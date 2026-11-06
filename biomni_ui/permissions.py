"""Permission for database connector calls: ask once, or let a scope remember the answer (Claude Science's connector scopes).

When the agent calls a database connector (ClinicalTrials, UniProt, PubMed and the others), the call is allowed only if:
- a standing grant covers it: granted for this conversation, for this project, or for everywhere (Settings → Remember and database), or
- the user allows it now, in the chat: once, or with a scope that is then stored.

A task that runs with no one to ask (the auto mode, scheduled runs) is refused unless a standing grant covers the call.
Tasks can run in worker processes, so the user's answer travels through a small file: the answer endpoint writes it and the
task polls for it. Grants are kept in ui_data/tool_grants.json.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent / "ui_data"
ANSWERS = ROOT / "permission_answers"
GRANTS = ROOT / "tool_grants.json"
CHOICES = ("once", "conversation", "project", "global", "deny")
SCOPES = ("conversation", "project", "global")
TIMEOUT_SECONDS = 600
POLL_SECONDS = 0.5
_lock = threading.Lock()


def _read_grants() -> dict[str, Any]:
    try:
        data = json.loads(GRANTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {
        "global": [str(t) for t in data.get("global", [])],
        "projects": {str(k): [str(t) for t in v] for k, v in (data.get("projects") or {}).items()},
        "conversations": {str(k): [str(t) for t in v] for k, v in (data.get("conversations") or {}).items()},
    }


def _write_grants(data: dict[str, Any]) -> None:
    GRANTS.parent.mkdir(parents=True, exist_ok=True)
    tmp = GRANTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(GRANTS)


def allowed(tool: str, conversation_id: str | None, project_id: str | None) -> bool:
    """True when a standing grant covers this tool for this conversation, this project, or everywhere."""
    data = _read_grants()
    if tool in data["global"]:
        return True
    if tool in data["projects"].get(project_id or "quick", []):  # the quick-task area is the project "quick"
        return True
    return bool(conversation_id) and tool in data["conversations"].get(conversation_id, [])


def add(scope: str, tool: str, conversation_id: str | None, project_id: str | None) -> None:
    if scope not in SCOPES:
        raise ValueError("scope must be conversation, project or global")
    with _lock:
        data = _read_grants()
        if scope == "global":
            key_list = data["global"]
        elif scope == "project":
            key_list = data["projects"].setdefault(project_id or "quick", [])
        else:
            if not conversation_id:
                raise ValueError("a conversation grant needs a conversation")
            key_list = data["conversations"].setdefault(conversation_id, [])
        if tool not in key_list:
            key_list.append(tool)
        _write_grants(data)


def remove(scope: str, tool: str, key: str | None = None) -> bool:
    """Revoke one standing grant. `key` is the conversation or project id for those scopes (ignored for global)."""
    with _lock:
        data = _read_grants()
        if scope == "global":
            target = data["global"]
        elif scope == "project":
            target = data["projects"].get(key or "", [])
        elif scope == "conversation":
            target = data["conversations"].get(key or "", [])
        else:
            return False
        if tool not in target:
            return False
        target.remove(tool)
        _write_grants(data)
        return True


def listing() -> list[dict[str, Any]]:
    data = _read_grants()
    rows = [{"scope": "global", "key": "", "tool": t} for t in data["global"]]
    rows += [{"scope": "project", "key": k, "tool": t} for k, ts in data["projects"].items() for t in ts]
    rows += [{"scope": "conversation", "key": k, "tool": t} for k, ts in data["conversations"].items() for t in ts]
    return rows


def answer(request_id: str, choice: str) -> bool:
    """The user's answer to one permission request, written for the task that is waiting."""
    if choice not in CHOICES or not request_id or not all(c.isalnum() or c in "-_" for c in request_id):
        return False
    ANSWERS.mkdir(parents=True, exist_ok=True)
    (ANSWERS / f"{request_id}.json").write_text(json.dumps({"choice": choice, "at": time.time()}), encoding="utf-8")
    return True


def _wait_answer(request_id: str, cancel: Callable[[], bool], timeout: float) -> str:
    path = ANSWERS / f"{request_id}.json"
    deadline = time.time() + timeout
    while time.time() < deadline and not cancel():
        if path.exists():
            try:
                choice = str(json.loads(path.read_text(encoding="utf-8")).get("choice") or "deny")
            except (OSError, ValueError):
                choice = "deny"
            try:
                path.unlink()
            except OSError:
                pass
            return choice
        time.sleep(POLL_SECONDS)
    return "deny"


def decide(tool: str, title: str, conversation_id: str | None, project_id: str | None, interactive: bool,
           emit: Callable[[dict[str, Any]], None], cancel: Callable[[], bool], timeout: float = TIMEOUT_SECONDS) -> str:
    """'allow' or 'deny' for one call of a database connector tool. Asks the user in the chat when it can (interactive)."""
    if allowed(tool, conversation_id, project_id):
        return "allow"
    if not interactive:
        return "deny"
    request_id = uuid.uuid4().hex[:16]
    emit({"type": "permission", "id": request_id, "tool": tool, "title": title, "choices": list(CHOICES)})
    choice = _wait_answer(request_id, cancel, timeout)
    if choice in SCOPES:
        add(choice, tool, conversation_id, project_id)
    return "allow" if choice in ("once", *SCOPES) else "deny"


# ---- database calls made from Python --------------------------------------------------------------
# The Python session runs in its own process. When a database function is called there, the kernel writes a request
# and waits. The task that owns the session answers it through the same decide() as the agent's own calls.
REQUESTS = ROOT / "permission_requests"
DECISIONS = ROOT / "permission_decisions"


def kernel_check(tool: str, title: str, session: str, timeout: float = TIMEOUT_SECONDS) -> bool:
    """Runs inside the Python session: ask the task that owns it whether this database call may run. Refused when nobody answers."""
    request_id = uuid.uuid4().hex[:16]
    REQUESTS.mkdir(parents=True, exist_ok=True)
    DECISIONS.mkdir(parents=True, exist_ok=True)
    (REQUESTS / f"{request_id}.json").write_text(json.dumps({"session": session, "tool": tool, "title": title}), encoding="utf-8")
    path = DECISIONS / f"{request_id}.json"
    deadline = time.time() + timeout
    verdict = "deny"
    try:
        while time.time() < deadline:
            if path.exists():
                try:
                    verdict = str(json.loads(path.read_text(encoding="utf-8")).get("decision") or "deny")
                except (OSError, ValueError):
                    verdict = "deny"
                break
            time.sleep(POLL_SECONDS)
    finally:
        for p in (REQUESTS / f"{request_id}.json", path):
            try:
                p.unlink()
            except OSError:
                pass
    return verdict == "allow"


def serve(session: str, decide_fn: Callable[[str], str], stop: threading.Event) -> None:
    """Runs beside one Python step of a task: answers the database requests its kernel raises, until `stop` is set."""
    served: set[str] = set()
    while not stop.is_set():
        try:
            pending = list(REQUESTS.glob("*.json")) if REQUESTS.exists() else []
        except OSError:
            pending = []
        for path in pending:
            rid = path.stem
            if rid in served:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("session") != session:
                continue
            served.add(rid)
            threading.Thread(target=_answer_kernel, args=(rid, str(data.get("tool") or ""), decide_fn, path), daemon=True).start()
        stop.wait(POLL_SECONDS)


def _answer_kernel(request_id: str, tool: str, decide_fn: Callable[[str], str], request_path: Path) -> None:
    try:
        verdict = decide_fn(tool)
    except Exception:  # a failed decision is a refusal, never a silent allow
        verdict = "deny"
    DECISIONS.mkdir(parents=True, exist_ok=True)
    (DECISIONS / f"{request_id}.json").write_text(json.dumps({"decision": "allow" if verdict == "allow" else "deny"}), encoding="utf-8")
    try:
        request_path.unlink()
    except OSError:
        pass
