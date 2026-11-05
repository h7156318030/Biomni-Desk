"""A short record of every model call a task makes: which model, which reasoning effort, how many tokens, how long.

The runner turns these into `llm` events, so the page can show what was actually used instead of what was asked for.
"""

from __future__ import annotations

import threading
from typing import Any

_CALLS: list[dict[str, Any]] = []
_LOCK = threading.Lock()


def record(call: dict[str, Any]) -> None:
    with _LOCK:
        _CALLS.append(call)


def drain() -> list[dict[str, Any]]:
    with _LOCK:
        out = list(_CALLS)
        _CALLS.clear()
        return out


def from_reply(reply: Any, *, model: str | None, effort: str | None, seconds: float) -> dict[str, Any]:
    """Build the record from a LangChain reply (token usage is in `usage_metadata` when the provider reports it)."""
    usage = getattr(reply, "usage_metadata", None) or {}
    meta = getattr(reply, "response_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    return {
        "model": meta.get("model") or model or "",
        "effort": meta.get("effort") or effort,
        "seconds": round(seconds, 1),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": details.get("reasoning"),
    }


# Live text: the model call in progress reports what it has written so far; the runner shows it while the call is open.
_SINK: Any = None


def set_draft_sink(fn: Any) -> None:
    global _SINK
    _SINK = fn


def push_draft(text: str) -> None:
    sink = _SINK
    if sink is not None:
        try:
            sink(text)
        except Exception:
            pass  # a display problem must never break the model call
