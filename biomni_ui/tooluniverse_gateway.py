"""A gateway to the ToolUniverse collection (public package `tooluniverse`): find a tool by keywords, then run it.

Two functions for the agent: `tooluniverse_search` lists matching tool names with what they do; `tooluniverse_run` calls one
with its arguments. The collection is loaded once per process (about 1–2 s); each call goes to the tool's own public API.
"""

from __future__ import annotations

import contextlib
import io
import json
import threading
from typing import Any

_LOCK = threading.Lock()
_TU: Any = None


def _engine() -> Any:
    global _TU
    with _LOCK:
        if _TU is None:
            from tooluniverse import ToolUniverse

            with contextlib.redirect_stdout(io.StringIO()):  # the package prints its own loading lines; they are not part of any answer
                tu = ToolUniverse()
                tu.load_tools()
            _TU = tu
        return _TU


def _tools() -> list[dict[str, Any]]:
    tu = _engine()
    return list(getattr(tu, "all_tools", []) or [])


def tooluniverse_search(query: str, limit: int = 10) -> str:
    """Tools in the ToolUniverse collection whose name or description contains every word of the query."""
    words = [w.lower() for w in (query or "").split() if w.strip()]
    if not words:
        return "Give a keyword, for example pubmed, clinvar or chembl."
    n = max(1, min(int(limit or 10), 50))
    hits = []
    for t in _tools():
        text = f"{t.get('name', '')} {t.get('description', '')}".lower()
        if all(w in text for w in words):
            hits.append(t)
    if not hits:
        return f"No ToolUniverse tool matches “{query}”."
    lines = [f"ToolUniverse tools matching “{query}” ({len(hits)} in all, first {min(n, len(hits))} listed):"]
    for t in hits[:n]:
        req = [p.get("name") for p in (t.get("parameter", {}) or {}).get("required", [])] if isinstance(t.get("parameter"), dict) else []
        lines.append(f"- {t.get('name')}: {' '.join(str(t.get('description', '')).split())[:160]}" + (f"(required parameters: {', '.join(req)})" if req else ""))
    return "\n".join(lines)


def tooluniverse_run(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Run one ToolUniverse tool by its exact name with its arguments; returns the JSON result (truncated)."""
    tool = (name or "").strip()
    if not tool:
        return "Give the tool name (find it with tooluniverse_search first)."
    args = arguments if isinstance(arguments, dict) else {}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            out = _engine().run({"name": tool, "arguments": args})
    except Exception as e:  # reported to the model like any failed step
        return f"ToolUniverse failed to run {tool}: {type(e).__name__}: {str(e)[:300]}"
    text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
    if len(text) > 6000:
        text = text[:5500] + f"\n... ({len(text) - 5500} characters omitted)"
    return text
