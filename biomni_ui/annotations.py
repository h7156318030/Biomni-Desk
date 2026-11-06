"""Comments on result files (Claude Science's annotations). A comment is pinned to a file, optionally to a quoted passage of it.

Pending comments are sent with the user's next message in the conversation: they are written into the task's text and then marked
as sent, with the task that carried them. Comments have no threads and no resolve state.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MAX_TEXT = 1000
MAX_QUOTE = 500
_lock = threading.Lock()


def _file(conv_dir: Path) -> Path:
    d = Path(conv_dir) / "execution_trace"
    d.mkdir(parents=True, exist_ok=True)
    return d / "annotations.json"


def _read(conv_dir: Path) -> list[dict[str, Any]]:
    try:
        return [a for a in json.loads(_file(conv_dir).read_text(encoding="utf-8")).get("items", []) if isinstance(a, dict)]
    except (OSError, ValueError, AttributeError):
        return []


def _write(conv_dir: Path, items: list[dict[str, Any]]) -> None:
    f = _file(conv_dir)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def list_items(conv_dir: Path) -> list[dict[str, Any]]:
    return sorted(_read(conv_dir), key=lambda a: a.get("created", 0))


def add(conv_dir: Path, path: str, text: str, quote: str = "") -> dict[str, Any]:
    text = " ".join(str(text or "").split())[:MAX_TEXT]
    if not text:
        raise ValueError("A comment needs some text.")
    if not str(path or "").strip():
        raise ValueError("A comment must be attached to a result file.")
    item = {"id": uuid.uuid4().hex[:10], "path": str(path), "quote": " ".join(str(quote or "").split())[:MAX_QUOTE],
            "text": text, "created": time.time(), "sent_in_task": None, "sent_at": None}
    with _lock:
        items = _read(conv_dir)
        items.append(item)
        _write(conv_dir, items)
    return item


def delete(conv_dir: Path, item_id: str) -> bool:
    with _lock:
        items = _read(conv_dir)
        kept = [a for a in items if a.get("id") != item_id]
        if len(kept) == len(items):
            return False
        _write(conv_dir, kept)
    return True


def take_pending(conv_dir: Path) -> list[dict[str, Any]]:
    """The comments not yet sent. The caller marks them sent once the task exists (see mark_sent)."""
    return [a for a in list_items(conv_dir) if a.get("sent_in_task") is None]


def mark_sent(conv_dir: Path, item_ids: list[str], task_id: str) -> None:
    if not item_ids:
        return
    with _lock:
        items = _read(conv_dir)
        now = time.time()
        for a in items:
            if a.get("id") in item_ids and a.get("sent_in_task") is None:
                a["sent_in_task"] = task_id
                a["sent_at"] = now
        _write(conv_dir, items)


def as_prompt_text(items: list[dict[str, Any]]) -> str:
    """The comments written as part of the user's message, so the agent reads them with the question."""
    if not items:
        return ""
    lines = ["The user left these comments on result files; take them into account for this request:"]
    for a in items:
        quote = f" (on the passage “{a['quote']}”)" if a.get("quote") else ""
        lines.append(f"- {a['path']}{quote}: {a['text']}")
    return "\n".join(lines)
