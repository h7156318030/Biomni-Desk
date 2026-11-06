"""What each project's tasks did, kept automatically after every finished task (no model call is needed to write it).

A later task in the same project gets the most relevant of these entries, so the agent knows what was done before even in a new
conversation. A project's switch for memory (Settings / project page) turns this off for that project. Entries from the same
conversation are not repeated: that conversation's own history already carries them."""

from __future__ import annotations

import json
import math
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from biomni_ui import notes as _notes

STORE = Path(__file__).resolve().parent.parent / "ui_data" / "work_log.json"
MAX_ITEMS = 300
QUESTION_CHARS = 200
ANSWER_CHARS = 420
DEFAULT_BUDGET = 1500
_lock = threading.Lock()


def _read() -> list[dict[str, Any]]:
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in data.get("items", []) if isinstance(i, dict) and i.get("id")]


def _write(items: list[dict[str, Any]]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STORE)


def record(project_id: str | None, conversation_id: str, task_id: str, question: str, answer: str) -> dict[str, Any] | None:
    """Keep one finished task. Empty questions or answers are not kept."""
    q = " ".join(str(question or "").split())[:QUESTION_CHARS]
    a = " ".join(str(answer or "").split())[:ANSWER_CHARS]
    if not q or not a:
        return None
    item = {"id": uuid.uuid4().hex[:10], "project_id": project_id or "quick", "conversation_id": conversation_id, "task_id": task_id,
            "question": q, "answer": a, "created": time.time()}
    with _lock:
        items = _read() + [item]
        _write(items[-MAX_ITEMS:])
    return item


def list_items(project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    items = [i for i in _read() if project_id is None or i.get("project_id") == project_id]
    return sorted(items, key=lambda i: i.get("created", 0), reverse=True)[:limit]


def delete(project_id: str | None = None) -> int:
    """Forget one project's entries, or all of them when project_id is None. Returns how many were removed."""
    with _lock:
        items = _read()
        kept = [i for i in items if project_id is not None and i.get("project_id") != project_id] if project_id is not None else []
        removed = len(items) - len(kept)
        if removed:
            _write(kept)
    return removed


def _score(query_terms: set[str], item: dict[str, Any]) -> float:
    terms = _notes._terms(f"{item.get('question', '')} {item.get('answer', '')}")
    shared = len(query_terms & terms)
    return shared / math.sqrt(len(query_terms) * len(terms)) if shared and query_terms and terms else 0.0


def block(project_id: str | None, query: str = "", exclude_conversation: str | None = None, budget: int | None = None, enabled: bool = True) -> str:
    """The earlier work of this project for a task's instructions: the entries that match the question best, then the most recent, within
    the budget. Empty when memory is off for the project or there is nothing to show."""
    if not enabled:
        return ""
    limit = int(budget) if budget else DEFAULT_BUDGET
    items = [i for i in _read() if i.get("project_id") == (project_id or "quick") and i.get("conversation_id") != exclude_conversation]
    if not items:
        return ""
    qt = _notes._terms(query)
    ranked = sorted(items, key=lambda i: (-_score(qt, i), -i.get("created", 0)))
    chosen, used = [], 0
    for i in ranked:
        line = f"- {i.get('question')} → {i.get('answer')}"
        if used + len(line) > limit:
            continue
        chosen.append(i)
        used += len(line)
    if not chosen:
        return ""
    chosen.sort(key=lambda i: i.get("created", 0))
    lines = ["## Earlier work in this project (recorded automatically from finished tasks; use it when the question refers to earlier work, "
             "and do not repeat work already done unless asked)"]
    lines += [f"- {i.get('question')} → {i.get('answer')}" for i in chosen]
    return "\n".join(lines)
