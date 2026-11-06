"""SQLite persistence for conversations, tasks and their event logs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, prompt TEXT NOT NULL,
    created REAL NOT NULL, status TEXT NOT NULL DEFAULT 'running'
);
CREATE INDEX IF NOT EXISTS tasks_conv ON tasks(conversation_id, created);
CREATE TABLE IF NOT EXISTS events (
    task_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY (task_id, seq)
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS project_settings (
    project_id TEXT PRIMARY KEY, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS published (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, task_id TEXT NOT NULL DEFAULT ''
);
"""

def _text_around(body: str, q: str) -> str:
    """A short piece of the readable text in a stored event that contains the query (the JSON keys and numbers are skipped)."""
    try:
        data: Any = json.loads(body)
    except ValueError:
        data = body
    strings: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            strings.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(data)
    for text in strings:
        at = text.lower().find(q.lower())
        if at >= 0:
            return text[max(0, at - 60): at + len(q) + 80]
    return ""


DEFAULT_PROJECT = "quick"
DEFAULT_PROJECT_NAME = "Quick task"


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            cols = {r["name"] for r in self._db.execute("PRAGMA table_info(conversations)")}
            if "project_id" not in cols:
                self._db.execute(f"ALTER TABLE conversations ADD COLUMN project_id TEXT NOT NULL DEFAULT '{DEFAULT_PROJECT}'")
            if "notes" not in cols:
                self._db.execute("ALTER TABLE conversations ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
            # A task that was still running when the server stopped can never finish.
            if not os.environ.get("BIOMNI_UI_WORKER"):  # a worker process starts while the server's tasks are running
                self._db.execute("UPDATE tasks SET status='interrupted' WHERE status='running'")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _run(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
            return rows

    def create_task(self, task_id: str, conversation_id: str, prompt: str) -> None:
        now = time.time()
        if not self._run("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)):
            title = " ".join(prompt.split())[:40] or "New task"
            self._run("INSERT INTO conversations (id, title, created, updated) VALUES (?,?,?,?)", (conversation_id, title, now, now))
        self._run("INSERT INTO tasks (id, conversation_id, prompt, created) VALUES (?,?,?,?)",
                  (task_id, conversation_id, prompt, now))
        self._run("UPDATE conversations SET updated=? WHERE id=?", (now, conversation_id))

    def recent_exchanges(self, conversation_id: str, n: int = 2) -> list[tuple[str, str]]:
        """(question, answer) of the last `n` finished tasks of a conversation, oldest first: context for pronouns."""
        out = []
        for t in self._run("SELECT id, prompt FROM tasks WHERE conversation_id=? ORDER BY created DESC LIMIT ?", (conversation_id, n)):
            answer = ""
            for e in self._run("SELECT body FROM events WHERE task_id=? ORDER BY seq", (t["id"],)):
                ev = json.loads(e["body"])
                if ev.get("type") == "answer":
                    answer = ev.get("text", "")
            out.append((t["prompt"], answer))
        return out[::-1]

    def task_count(self, conversation_id: str) -> int:
        return self._run("SELECT COUNT(*) AS n FROM tasks WHERE conversation_id=?", (conversation_id,))[0]["n"]

    def add_event(self, task_id: str, event: dict[str, Any]) -> None:
        self._run("INSERT OR REPLACE INTO events VALUES (?,?,?)",
                  (task_id, event["seq"], json.dumps(event, ensure_ascii=False)))

    def next_seq(self, task_id: str) -> int:
        return self._run("SELECT COALESCE(MAX(seq)+1, 0) AS n FROM events WHERE task_id=?", (task_id,))[0]["n"]

    def set_status(self, task_id: str, status: str) -> None:
        self._run("UPDATE tasks SET status=? WHERE id=?", (status, task_id))

    def list_conversations(self) -> list[dict[str, Any]]:
        rows = self._run(
            "SELECT c.id, c.title, c.created, c.updated, c.project_id, "
            "(SELECT status FROM tasks t WHERE t.conversation_id=c.id ORDER BY t.created DESC LIMIT 1) AS status "
            "FROM conversations c ORDER BY c.updated DESC"
        )
        return [dict(r) for r in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        conv = self._run("SELECT id, title, created, updated, project_id, notes FROM conversations WHERE id=?", (conversation_id,))
        if not conv:
            return None
        out = dict(conv[0])
        out["tasks"] = []
        for t in self._run("SELECT id, prompt, created, status FROM tasks WHERE conversation_id=? ORDER BY created",
                           (conversation_id,)):
            events = [json.loads(e["body"]) for e in
                      self._run("SELECT body FROM events WHERE task_id=? ORDER BY seq", (t["id"],))]
            out["tasks"].append({**dict(t), "events": events})
        return out

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self._run("SELECT id, conversation_id, prompt, status FROM tasks WHERE id=?", (task_id,))
        return dict(rows[0]) if rows else None

    def rename(self, conversation_id: str, title: str) -> bool:
        n = self._run("SELECT 1 FROM conversations WHERE id=?", (conversation_id,))
        if n:
            self._run("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:80] or "New task", conversation_id))
        return bool(n)

    def delete_conversation(self, conversation_id: str) -> None:
        ids = [r["id"] for r in self._run("SELECT id FROM tasks WHERE conversation_id=?", (conversation_id,))]
        for tid in ids:
            self._run("DELETE FROM events WHERE task_id=?", (tid,))
        self._run("DELETE FROM tasks WHERE conversation_id=?", (conversation_id,))
        self._run("DELETE FROM conversations WHERE id=?", (conversation_id,))

    # -- projects ---------------------------------------------------------------------------------------------
    def list_projects(self) -> list[dict[str, Any]]:
        rows = self._run("SELECT id, name, created FROM projects ORDER BY created")
        counts = {r["project_id"]: r["n"] for r in self._run("SELECT project_id, COUNT(*) AS n FROM conversations GROUP BY project_id")}
        default = {"id": DEFAULT_PROJECT, "name": DEFAULT_PROJECT_NAME, "created": 0, "default": True}
        return [{**p, "count": counts.get(p["id"], 0)} for p in [default, *({**dict(r), "default": False} for r in rows)]]

    def create_project(self, name: str) -> dict[str, Any]:
        name = " ".join(name.split())[:40]
        if not name:
            raise ValueError("The project name cannot be empty")
        if name == DEFAULT_PROJECT_NAME or any(p["name"] == name for p in self.list_projects()):
            raise ValueError("A project with this name already exists")
        pid = "p" + str(int(time.time() * 1000))[-9:]
        self._run("INSERT INTO projects VALUES (?,?,?)", (pid, name, time.time()))
        return {"id": pid, "name": name, "default": False, "count": 0}

    def rename_project(self, project_id: str, name: str) -> bool:
        name = " ".join(name.split())[:40]
        if not name or project_id == DEFAULT_PROJECT or not self._run("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            return False
        self._run("UPDATE projects SET name=? WHERE id=?", (name, project_id))
        return True

    def delete_project(self, project_id: str) -> bool:
        """Its tasks are kept and move back to the default project."""
        if project_id == DEFAULT_PROJECT or not self._run("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            return False
        self._run("UPDATE conversations SET project_id=? WHERE project_id=?", (DEFAULT_PROJECT, project_id))
        self._run("DELETE FROM projects WHERE id=?", (project_id,))
        return True

    def _in_list(self, ids: list[str]) -> tuple[str, tuple]:
        return ",".join("?" for _ in ids), tuple(ids)

    def project_summary(self, project_id: str) -> dict[str, Any]:
        """What deleting this project would remove: its sessions, their tasks and the published pages made from them."""
        conv_ids = [r["id"] for r in self._run("SELECT id FROM conversations WHERE project_id=?", (project_id,))]
        if not conv_ids:
            return {"sessions": 0, "tasks": 0, "published": 0}
        marks, args = self._in_list(conv_ids)
        task_ids = [r["id"] for r in self._run(f"SELECT id FROM tasks WHERE conversation_id IN ({marks})", args)]
        published = 0
        if task_ids:
            tmarks, targs = self._in_list(task_ids)
            published = self._run(f"SELECT COUNT(*) AS n FROM published WHERE task_id IN ({tmarks})", targs)[0]["n"]
        return {"sessions": len(conv_ids), "tasks": len(task_ids), "published": published}

    def delete_project_cascade(self, project_id: str) -> list[str]:
        """Delete a project with its sessions, their tasks and events, the published records made from them, and its settings.
        Returns the deleted conversation ids so the caller can remove their working folders. The default project cannot be deleted."""
        if project_id == DEFAULT_PROJECT or not self._run("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            return []
        conv_ids = [r["id"] for r in self._run("SELECT id FROM conversations WHERE project_id=?", (project_id,))]
        if conv_ids:
            marks, args = self._in_list(conv_ids)
            task_ids = [r["id"] for r in self._run(f"SELECT id FROM tasks WHERE conversation_id IN ({marks})", args)]
            if task_ids:
                tmarks, targs = self._in_list(task_ids)
                self._run(f"DELETE FROM events WHERE task_id IN ({tmarks})", targs)
                self._run(f"DELETE FROM published WHERE task_id IN ({tmarks})", targs)
                self._run(f"DELETE FROM tasks WHERE id IN ({tmarks})", targs)
            self._run(f"DELETE FROM conversations WHERE id IN ({marks})", args)
        self._run("DELETE FROM project_settings WHERE project_id=?", (project_id,))
        self._run("DELETE FROM projects WHERE id=?", (project_id,))
        return conv_ids

    def search(self, query: str, project_id: str | None = None, limit: int = 40) -> list[dict[str, Any]]:
        """Sessions whose title, question or any step text contains the query (case-insensitive for ASCII), newest first."""
        q = " ".join(str(query or "").split())
        if not q:
            return []
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{esc}%"
        rows = self._run(
            "SELECT c.id, c.title, c.updated, c.project_id, "
            "(SELECT t.prompt FROM tasks t WHERE t.conversation_id=c.id AND t.prompt LIKE ? ESCAPE '\\' ORDER BY t.created LIMIT 1) AS prompt_hit, "
            "(SELECT e.body FROM events e JOIN tasks t ON t.id=e.task_id WHERE t.conversation_id=c.id AND e.body LIKE ? ESCAPE '\\' LIMIT 1) AS event_hit "
            "FROM conversations c "
            "WHERE (? IS NULL OR c.project_id=?) AND (c.title LIKE ? ESCAPE '\\' "
            "OR EXISTS (SELECT 1 FROM tasks t WHERE t.conversation_id=c.id AND t.prompt LIKE ? ESCAPE '\\') "
            "OR EXISTS (SELECT 1 FROM events e JOIN tasks t ON t.id=e.task_id WHERE t.conversation_id=c.id AND e.body LIKE ? ESCAPE '\\')) "
            "ORDER BY c.updated DESC LIMIT ?",
            (like, like, project_id, project_id, like, like, like, limit),
        )
        out = []
        for r in rows:
            snippet = str(r["prompt_hit"] or "")
            if not snippet and r["event_hit"]:
                snippet = _text_around(str(r["event_hit"]), q)
            out.append({"id": r["id"], "title": r["title"], "updated": r["updated"], "project_id": r["project_id"] or DEFAULT_PROJECT, "snippet": snippet.replace("\\n", " ")})
        return out

    def set_project(self, conversation_id: str, project_id: str) -> bool:
        if project_id != DEFAULT_PROJECT and not self._run("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            return False
        if not self._run("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)):
            return False
        self._run("UPDATE conversations SET project_id=? WHERE id=?", (project_id, conversation_id))
        return True

    # -- notes ------------------------------------------------------------------------------------------------
    def get_notes(self, conversation_id: str) -> str | None:
        rows = self._run("SELECT notes FROM conversations WHERE id=?", (conversation_id,))
        return rows[0]["notes"] if rows else None

    def set_notes(self, conversation_id: str, text: str) -> bool:
        if not self._run("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)):
            return False
        self._run("UPDATE conversations SET notes=? WHERE id=?", (text[:20000], conversation_id))
        return True

    # -- published results ------------------------------------------------------------------------------------
    def add_published(self, pub_id: str, title: str, task_id: str = "") -> None:
        self._run("INSERT INTO published VALUES (?,?,?,?)", (pub_id, title.strip()[:100] or "Untitled result", time.time(), task_id))

    def list_published(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._run("SELECT id, title, created, task_id FROM published ORDER BY created DESC")]

    def delete_published(self, pub_id: str) -> bool:
        n = self._run("SELECT 1 FROM published WHERE id=?", (pub_id,))
        if n:
            self._run("DELETE FROM published WHERE id=?", (pub_id,))
        return bool(n)

    # -- usage ------------------------------------------------------------------------------------------------
    def usage(self, days: int = 14) -> dict[str, Any]:
        """Counts for the usage panel: tasks per day, how they ended, and how much code ran."""
        now = time.time()
        since = now - days * 86400
        rows = self._run("SELECT created, status FROM tasks")
        by_day: dict[str, int] = {}
        status: dict[str, int] = {}
        for r in rows:
            status[r["status"]] = status.get(r["status"], 0) + 1
            if r["created"] >= since:
                day = time.strftime("%Y-%m-%d", time.localtime(r["created"]))
                by_day[day] = by_day.get(day, 0) + 1
        runs = seconds = 0.0
        for r in self._run("SELECT body FROM events"):
            if '"type": "code"' in r["body"] or '"type": "observation"' in r["body"]:
                e = json.loads(r["body"])
                if e.get("type") == "code":
                    runs += 1
                elif e.get("type") == "observation":
                    seconds += float(e.get("elapsed") or 0)
        # one entry per day, oldest first, including empty days
        series = []
        for i in range(days - 1, -1, -1):
            day = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
            series.append({"day": day, "tasks": by_day.get(day, 0)})
        return {
            "tasks_total": len(rows),
            "status": status,
            "series": series,
            "code_runs": int(runs),
            "code_seconds": round(seconds, 1),
            "conversations": len(self.list_conversations()),
        }

    # -- per-project settings (context, instructions, auto-attached skills) -----------------------------------
    def get_project_settings(self, project_id: str) -> dict[str, Any]:
        rows = self._run("SELECT body FROM project_settings WHERE project_id=?", (project_id,))
        try:
            data = json.loads(rows[0]["body"]) if rows else {}
        except ValueError:
            data = {}
        return {
            "context": str(data.get("context") or ""),
            "instructions": list(data.get("instructions") or []),
            "skills": list(data.get("skills") or []),
            "files": list(data.get("files") or []),
            "tools_off": list(data.get("tools_off") or []),
            "memory_on": bool(data.get("memory_on", True)),
        }

    def generated_files(self, project_id: str, limit: int = 80) -> list[dict[str, Any]]:
        """The result files the project's sessions produced, newest first, one entry per file path."""
        rows = self._run(
            "SELECT e.body, t.conversation_id, c.title, t.created FROM events e "
            "JOIN tasks t ON t.id = e.task_id JOIN conversations c ON c.id = t.conversation_id "
            "WHERE c.project_id=? AND e.body LIKE '%\"artifacts\": [{%' ORDER BY t.created DESC, e.seq DESC LIMIT 400",
            (project_id,),
        )
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                data = json.loads(r["body"])
            except ValueError:
                continue
            for a in data.get("artifacts") or []:
                path = str(a.get("path") or "")
                if not path or path in seen:
                    continue
                seen.add(path)
                out.append({"name": a.get("name") or path, "path": path, "kind": a.get("kind"), "size": a.get("size"),
                            "session_id": r["conversation_id"], "session_title": r["title"], "time": r["created"]})
                if len(out) >= limit:
                    return out
        return out

    def set_project_settings(self, project_id: str, value: dict[str, Any]) -> bool:
        if project_id != DEFAULT_PROJECT and not self._run("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            return False
        self._run("INSERT OR REPLACE INTO project_settings VALUES (?,?)", (project_id, json.dumps(value, ensure_ascii=False)))
        return True

    def conversation_project(self, conversation_id: str | None) -> str:
        if not conversation_id:
            return DEFAULT_PROJECT
        rows = self._run("SELECT project_id FROM conversations WHERE id=?", (conversation_id,))
        return rows[0]["project_id"] if rows else DEFAULT_PROJECT

    def recent_files(self, project_id: str, exclude_conversation: str | None = None, limit: int = 8) -> list[str]:
        """Names of result files earlier tasks in this project produced, newest first."""
        rows = self._run(
            "SELECT e.body FROM events e JOIN tasks t ON t.id = e.task_id JOIN conversations c ON c.id = t.conversation_id "
            "WHERE c.project_id=? AND c.id != ? AND e.body LIKE '%\"artifacts\": [{%' ORDER BY t.created DESC, e.seq DESC LIMIT 60",
            (project_id, exclude_conversation or ""),
        )
        names: list[str] = []
        for r in rows:
            for a in json.loads(r["body"]).get("artifacts") or []:
                name = a.get("path") or a.get("name")
                if name and name not in names:
                    names.append(name)
        return names[:limit]

    def data_info(self) -> dict[str, Any]:
        return {
            "conversations": self._run("SELECT COUNT(*) AS n FROM conversations")[0]["n"],
            "tasks": self._run("SELECT COUNT(*) AS n FROM tasks")[0]["n"],
            "events": self._run("SELECT COUNT(*) AS n FROM events")[0]["n"],
            "published": self._run("SELECT COUNT(*) AS n FROM published")[0]["n"],
        }

    def export_all(self) -> dict[str, Any]:
        convs = [self.get_conversation(c["id"]) for c in self.list_conversations()]
        return {"exported": time.time(), "projects": self.list_projects(), "conversations": convs}

    def delete_all_conversations(self) -> int:
        n = self._run("SELECT COUNT(*) AS n FROM conversations")[0]["n"]
        self._run("DELETE FROM events")
        self._run("DELETE FROM tasks")
        self._run("DELETE FROM conversations")
        return n
