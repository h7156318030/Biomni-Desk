"""A fixed answer-quality benchmark for the agent: each question has the tools a good run should use, facts a correct answer must contain,
and whether it must cite a source. Scoring reads a finished task's events from the database, so a change can be compared with the run before it.

What is measured (per question): the run finished without errors; an expected tool was called; each fact appears in the answer; a source is
cited where one is required; identifiers and figures in the answer that no tool output contains (audit); the flags of the second reader; and
the time and reasoning tokens spent. Facts are checked as substrings, so the questions are written to have one clear answer.

Run it against the running service:  python -m biomni_ui.evalbench run <label> [id,id,...]
Summarise a saved run:              python -m biomni_ui.evalbench summary <results.json>
Score saved tasks again:            python -m biomni_ui.evalbench rescore <results.json>
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).resolve().parent / "evalbench_questions.json"
RESULTS = ROOT / "ui_data" / "evalbench"
DB = ROOT / "ui_data" / "biomni_ui.db"
API = "http://127.0.0.1:8765"
_SOURCE = re.compile(r"https?://|\bPMID\s*[:：]?\s*\d{6,9}|\bDOI\b|10\.\d{4,9}/|\bNCT\d{8}\b", re.I)


def load_questions() -> list[dict[str, Any]]:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]


def _answer(events: list[dict[str, Any]]) -> str:
    return next((str(e.get("text") or "") for e in events if e.get("type") == "answer"), "")


def score(question: dict[str, Any], status: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    from biomni_ui import audit

    answer = _answer(events)
    seen = "\n".join([question["question"], audit.evidence_from_events(events)])
    code = "\n".join(str(e.get("code") or "") for e in events if e.get("type") == "code")
    tools = question.get("tools") or []
    facts = question.get("facts") or []
    fact_ok = [any(s.lower() in answer.lower() for s in group) for group in facts]
    llm = [e for e in events if e.get("type") == "llm"]
    return {
        "id": question["id"],
        "category": question.get("category", ""),
        "status": status,
        "errors": sum(1 for e in events if e.get("type") == "error"),
        "tool_expected": bool(tools),
        "tool_hit": (any(t in code for t in tools) if tools else None),
        "tool_calls": sum(1 for e in events if e.get("type") == "code"),
        "facts_total": len(facts),
        "facts_ok": sum(fact_ok),
        "facts_rate": (sum(fact_ok) / len(facts)) if facts else None,
        "source_required": bool(question.get("must_source")),
        "source_ok": (bool(_SOURCE.search(answer)) if question.get("must_source") else None),
        "unsupported_ids": len(audit.unsupported(answer, seen)),
        "ungrounded": len(audit.ungrounded(answer, seen)),
        "llm_calls": len(llm),
        "llm_seconds": round(sum(float(e.get("seconds") or 0) for e in llm), 1),
        "reasoning_tokens": sum(int(e.get("reasoning_tokens") or 0) for e in llm),
        "answer_chars": len(answer),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 3) if xs else None

    tool_rows = [r for r in rows if r["tool_expected"]]
    src_rows = [r for r in rows if r["source_required"]]
    return {
        "questions": len(rows),
        "finished": sum(1 for r in rows if r["status"] == "done"),
        "with_errors": sum(1 for r in rows if r["errors"]),
        "facts_rate": mean([r["facts_rate"] for r in rows if r["facts_rate"] is not None]),
        "tool_hit_rate": mean([1.0 if r["tool_hit"] else 0.0 for r in tool_rows]),
        "source_rate": mean([1.0 if r["source_ok"] else 0.0 for r in src_rows]),
        "unsupported_ids_total": sum(r["unsupported_ids"] for r in rows),
        "ungrounded_total": sum(r["ungrounded"] for r in rows),
        "llm_seconds_total": round(sum(r["llm_seconds"] for r in rows), 1),
        "reasoning_tokens_total": sum(r["reasoning_tokens"] for r in rows),
    }


def _status(con: sqlite3.Connection, task_id: str) -> str:
    row = con.execute("select status from tasks where id=?", (task_id,)).fetchone()
    return row[0] if row else "missing"


def _events(con: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(b) for (b,) in con.execute("select body from events where task_id=? order by seq", (task_id,))]


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _idle(timeout: int = 1200) -> bool:
    """Wait until the service is not busy with another task (it runs one at a time)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(API + "/api/health", timeout=10) as r:
                if not json.loads(r.read().decode("utf-8")).get("busy"):
                    return True
        except OSError:
            pass
        time.sleep(3)
    return False


def run(label: str, only: set[str] | None = None, mode: str = "auto") -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows: list[dict[str, Any]] = []
    out = RESULTS / f"{label}-{time.strftime('%Y%m%d-%H%M')}.json"
    for q in load_questions():
        if only and q["id"] not in only:
            continue
        if not _idle():
            raise RuntimeError("the service stayed busy; not starting a question")
        task = _post("/api/tasks", {"prompt": q["question"], "mode": mode})
        while True:
            status = _status(db, task["id"])
            if status not in ("running", "queued", "missing"):
                break
            time.sleep(5)
        row = score(q, status, _events(db, task["id"]))
        row["task_id"] = task["id"]
        rows.append(row)
        out.write_text(json.dumps({"label": label, "rows": rows, "summary": summarise(rows)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{q['id']} {status} facts {row['facts_ok']}/{row['facts_total']} tool {row['tool_hit']} "
              f"unsupported {row['unsupported_ids']} ungrounded {row['ungrounded']} {row['llm_seconds']}s", flush=True)
    return out


def rescore(results: Path) -> Path:
    """Score the same tasks again with the current question definitions (the events are kept, so no question is run again)."""
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    data = json.loads(results.read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in load_questions()}
    rows = []
    for old_row in data["rows"]:
        status = _status(db, old_row["task_id"])
        row = score(questions[old_row["id"]], status, _events(db, old_row["task_id"]))
        row["task_id"] = old_row["task_id"]
        rows.append(row)
    out = results.with_name(results.stem + "-rescored.json")
    out.write_text(json.dumps({"label": data.get("label", "") + " (rescored)", "rows": rows, "summary": summarise(rows)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "run":
        only = set(argv[2].split(",")) if len(argv) > 2 else None
        print("saved", run(argv[1], only))
        return 0
    if len(argv) == 2 and argv[0] == "rescore":
        print("saved", rescore(Path(argv[1])))
        return 0
    if len(argv) == 2 and argv[0] == "summary":
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        print(json.dumps(data.get("summary") or summarise(data["rows"]), ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
