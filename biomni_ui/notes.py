"""What the user asked to be remembered ("remember …" or "记住 …"), kept across tasks and conversations, the way Hermes keeps a user profile
and Claude Science keeps its instructions. Only the user writes these, by saying "remember …"; the model cannot add to them.

A message that is only a remember command (no question in it) is stored and answered without a model call. Stored notes go into the
instructions of every later task, so a species, a preference or a standing rule holds until it is deleted.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

STORE = Path(__file__).resolve().parent.parent / "ui_data" / "memory_notes.json"
MAX_ITEMS = 50
MAX_CHARS = 300
# English "remember" and the Chinese 记住 both work; a leading "please" / 请 / 帮我 / 麻烦 is allowed.
COMMAND = re.compile(r"^\s*(?:请|帮我|麻烦|please\s+)?\s*(?:记住|remember\b)[：:，,\s]*(.+?)\s*$", re.S | re.I)
_lock = threading.Lock()


def parse(prompt: str) -> str | None:
    """The text to remember when the whole message is a remember command, else None. A message with a question in it is a task, not a note."""
    text = str(prompt or "")
    if len(text) > 200 or re.search(r"[？?]", text):
        return None
    m = COMMAND.match(text)
    if not m:
        return None
    note = m.group(1).strip()
    return note[:MAX_CHARS] if note else None


def _read() -> list[dict[str, Any]]:
    """The stored notes; an unreadable or missing store reads as empty."""
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return [i for i in data.get("items", []) if isinstance(i, dict) and i.get("id") and i.get("text")]
    except (OSError, ValueError, AttributeError):
        return []


def _write(items: list[dict[str, Any]]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


def list_items() -> list[dict[str, Any]]:
    return sorted(_read(), key=lambda i: float(i.get("created") or 0))


def add(text: str) -> dict[str, Any]:
    """Store one note. The same text twice is not stored twice; past MAX_ITEMS the oldest is dropped."""
    text = str(text or "").strip()[:MAX_CHARS]
    with _lock:
        items = _read()
        for i in items:
            if i["text"] == text:
                return i
        item = {"id": uuid.uuid4().hex[:10], "text": text, "created": time.time()}
        items.append(item)
        items = sorted(items, key=lambda i: float(i.get("created") or 0))[-MAX_ITEMS:]
        _write(items)
    return item


def delete(item_id: str) -> bool:
    with _lock:
        items = _read()
        kept = [i for i in items if i["id"] != item_id]
        if len(kept) == len(items):
            return False
        _write(kept)
    return True


def block() -> str:
    """The notes for a task's instructions, or nothing when there are none. The heading is model-facing, so it stays in Chinese."""
    items = list_items()
    if not items:
        return ""
    lines = ["## Things the user asked to remember (said earlier; still in force for this task; if they conflict with the question, the question wins)"]
    lines += [f"- {i['text']}" for i in items]
    return "\n".join(lines)
