"""A session as a notebook: the questions, code steps with their output, tool calls and answers, in the order they happened.

Built only from what the session already stored (its events), so it never calls a model. A code step's output is the observation
that follows it; a question starts each task. Long outputs are cut, the full text stays in the session.
"""

from __future__ import annotations

import platform
import sys
from typing import Any

OUTPUT_CHARS = 4000
ANSWER_CHARS = 8000


def environment() -> dict[str, str]:
    return {"python": sys.version.split()[0], "platform": platform.platform()}


def build(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for t in conversation.get("tasks", []) or []:
        task_id = t.get("id", "")
        cells.append({"kind": "question", "task_id": task_id, "text": str(t.get("prompt") or "")})
        open_code: dict[str, Any] | None = None  # the code cell still waiting for its output
        for e in t.get("events", []) or []:
            kind = e.get("type")
            if kind == "code":
                open_code = {"kind": "code", "task_id": task_id, "language": str(e.get("language") or ""), "code": str(e.get("code") or ""),
                             "output": "", "files": [], "elapsed": e.get("elapsed")}
                cells.append(open_code)
            elif kind == "observation":
                if open_code is not None and not open_code["output"]:
                    open_code["output"] = str(e.get("text") or "")[:OUTPUT_CHARS]
                    open_code["files"] = list(e.get("files") or [])
                open_code = None
            elif kind == "tool":
                open_code = None
                cells.append({"kind": "tool", "task_id": task_id, "tool": str(e.get("tool") or ""), "query": str(e.get("query") or "")})
            elif kind == "answer":
                open_code = None
                cells.append({"kind": "answer", "task_id": task_id, "text": str(e.get("text") or "")[:ANSWER_CHARS]})
    return cells
