"""What is remembered across tasks and conversations, the way Hermes keeps a user profile and Claude Science keeps project instructions.

Two ways a note gets in, and both end with the user:
- The user says "remember …" or "记住 …": the note is saved at once, as before.
- The agent may call `propose_memory` during a task. That creates a *proposed* note, which is not used anywhere until the user
  approves it in Settings → Memory. A proposal never changes the instructions by itself.

Each note has a scope: all projects (project_id None) or one project. A task's instructions include the approved notes for all
projects and for the task's own project.

A message that is only a remember command (no question in it) is stored and answered without a model call.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

STORE = Path(__file__).resolve().parent.parent / "ui_data" / "memory_notes.json"
MAX_ITEMS = 200
DEFAULT_CATEGORY = "General"
MAX_CHARS = 300
APPROVED = "approved"
PROPOSED = "proposed"
SOURCES = ("you", "agent", "auto")  # you: typed by the user; agent: proposed by propose_memory; auto: suggested after a finished task
RECALL_CHARS = 1500  # the most remembered text one task's instructions carry; the rest stays saved for tasks it matches
RECALL_COUNT = 12
LEARN_MAX = 3  # at most this many suggestions from one finished task
_UNSET = object()
_STOP = {"the", "and", "for", "with", "what", "how", "can", "you", "use", "this", "that", "from", "are", "was", "not", "all", "any", "please", "about", "your"}
_WORD = re.compile(r"[a-z0-9][a-z0-9_.\-]*")
_CJK = re.compile(r"[㐀-鿿豈-﫿]+")
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


def _normal(i: dict[str, Any]) -> dict[str, Any]:
    """Older notes have no status or scope: they were the user's own notes for every project."""
    return {
        "id": str(i["id"]),
        "text": str(i["text"]),
        "created": float(i.get("created") or 0),
        "status": i.get("status") if i.get("status") in (APPROVED, PROPOSED) else APPROVED,
        "project_id": i.get("project_id") or None,
        "category": str(i.get("category") or DEFAULT_CATEGORY).strip()[:40] or DEFAULT_CATEGORY,
        "source": i.get("source") if i.get("source") in SOURCES else "you",
    }


def _read() -> list[dict[str, Any]]:
    """The stored notes; an unreadable or missing store reads as empty."""
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return [_normal(i) for i in data.get("items", []) if isinstance(i, dict) and i.get("id") and i.get("text")]
    except (OSError, ValueError, AttributeError, KeyError):
        return []


def _write(items: list[dict[str, Any]]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


def list_items() -> list[dict[str, Any]]:
    return sorted(_read(), key=lambda i: i["created"])


def add(text: str, project_id: str | None = None, status: str = APPROVED, category: str = DEFAULT_CATEGORY, source: str = "you") -> dict[str, Any]:
    """Store one note. The same text in the same scope twice is not stored twice; past MAX_ITEMS the oldest is dropped."""
    text = str(text or "").strip()[:MAX_CHARS]
    category = str(category or DEFAULT_CATEGORY).strip()[:40] or DEFAULT_CATEGORY
    with _lock:
        items = _read()
        for i in items:
            if i["text"] == text and i["project_id"] == (project_id or None):
                if status == APPROVED and i["status"] == PROPOSED:
                    i["status"] = APPROVED
                    _write(items)
                return i
        item = {"id": uuid.uuid4().hex[:10], "text": text, "created": time.time(), "status": status, "project_id": project_id or None,
                "category": category, "source": source}
        items.append(item)
        items = sorted(items, key=lambda i: i["created"])[-MAX_ITEMS:]
        _write(items)
    return item


def propose(text: str, project_id: str | None = None, category: str = DEFAULT_CATEGORY) -> dict[str, Any]:
    """A note the agent suggests. It waits for the user's approval and is not used until then."""
    return add(text, project_id, status=PROPOSED, category=category, source="agent")


def approve(item_id: str) -> bool:
    with _lock:
        items = _read()
        hit = next((i for i in items if i["id"] == item_id), None)
        if hit is None:
            return False
        hit["status"] = APPROVED
        _write(items)
    return True


def delete(item_id: str) -> bool:
    with _lock:
        items = _read()
        kept = [i for i in items if i["id"] != item_id]
        if len(kept) == len(items):
            return False
        _write(kept)
    return True


def delete_project(project_id: str) -> int:
    """Remove the notes that belong only to one project (notes for all projects stay). Returns how many were removed."""
    with _lock:
        items = _read()
        kept = [i for i in items if i["project_id"] != project_id]
        if len(kept) != len(items):
            _write(kept)
        return len(items) - len(kept)


def count_for_project(project_id: str) -> int:
    return sum(1 for i in list_items() if i["project_id"] == project_id)


def block(project_id: str | None = None, enabled: bool = True) -> str:
    """The approved notes for a task's instructions: all-project notes plus the task's own project. Nothing when there are none,
    or when memory is switched off for the project. The heading is model-facing, so it stays in Chinese."""
    if not enabled:
        return ""
    items = [i for i in list_items() if i["status"] == APPROVED and (i["project_id"] is None or i["project_id"] == project_id)]
    if not items:
        return ""
    lines = ["## Things the user asked to remember (said earlier; still in force for this task; if they conflict with the question, the question wins)"]
    lines += [f"- {i['text']}" for i in items]
    return "\n".join(lines)


def _terms(text: str) -> set[str]:
    """Words for matching: Latin words and numbers as they are, Chinese as two-character pieces (a lone character stays as it is)."""
    s = str(text or "").lower()
    out = {w for w in _WORD.findall(s) if w not in _STOP}
    for run in _CJK.findall(s):
        if len(run) == 1:
            out.add(run)
        else:
            out.update(run[k:k + 2] for k in range(len(run) - 1))
    return out


def _score(query_terms: set[str], item: dict[str, Any]) -> float:
    """How closely a note matches the question: shared terms, scaled by the size of both (cosine-like), so a long note does not win by length."""
    nt = _terms(f"{item['text']} {item['category']}")
    shared = len(query_terms & nt)
    if not shared:
        return 0.0
    return shared / math.sqrt(len(query_terms) * len(nt))


def recall(query: str, project_id: str | None = None, enabled: bool = True, budget: int | None = None) -> str:
    """The approved notes to put in one task's instructions, chosen for the question. When everything fits the budget, all of it is used.
    Otherwise the notes that share terms with the question are used, best match first, within the budget (Settings; RECALL_CHARS by
    default). A note that matches nothing is left out of this task, but stays saved. Empty when memory is off, or when nothing is in scope."""
    if not enabled:
        return ""
    limit = int(budget) if budget else RECALL_CHARS
    items = [i for i in list_items() if i["status"] == APPROVED and (i["project_id"] is None or i["project_id"] == project_id)]
    if not items:
        return ""
    qt = _terms(query)
    if sum(len(i["text"]) for i in items) <= limit and len(items) <= RECALL_COUNT:
        chosen = items
    else:
        scored = sorted(((_score(qt, i) if qt else 0.0, i) for i in items), key=lambda x: (-x[0], -x[1]["created"]))
        chosen, used = [], 0
        for s, i in scored:
            if len(chosen) >= RECALL_COUNT or (qt and s <= 0):
                break  # sorted by score, so nothing after this matches either
            if used + len(i["text"]) > limit:
                continue
            chosen.append(i)
            used += len(i["text"])
        chosen.sort(key=lambda i: i["created"])
    if not chosen:
        return ""
    lines = ["## Things the user asked to remember (said earlier; still in force for this task; if they conflict with the question, the question wins)"]
    lines += [f"- {i['text']}" for i in chosen]
    return "\n".join(lines)


def search(query: str = "", status: str | None = None) -> list[dict[str, Any]]:
    """Notes whose text or category matches the query (any project), newest first. An empty query lists them all."""
    ql = str(query or "").strip().lower()
    qt = _terms(ql)
    out = []
    for i in list_items():
        if status and i["status"] != status:
            continue
        hay = f"{i['text']} {i['category']}".lower()
        if ql and ql not in hay and not (qt and qt & _terms(hay)):
            continue
        out.append(i)
    return out[::-1]


def update(item_id: str, text: str | None = None, category: str | None = None, project_id: Any = _UNSET) -> dict[str, Any] | None:
    """Edit a note's text, category or scope. Only the fields given change. None when there is no such note; ValueError for empty text."""
    with _lock:
        items = _read()
        hit = next((i for i in items if i["id"] == item_id), None)
        if hit is None:
            return None
        if text is not None:
            clean = str(text).strip()[:MAX_CHARS]
            if not clean:
                raise ValueError("A note cannot be empty.")
            hit["text"] = clean
        if category is not None:
            hit["category"] = str(category).strip()[:40] or DEFAULT_CATEGORY
        if project_id is not _UNSET:
            hit["project_id"] = project_id or None
        _write(items)
    return hit


LEARN_SYSTEM = (
    "You keep a short memory for a research assistant. From the exchange below, pick at most three facts that will still matter in a later, "
    "different task: a standing preference of the user (output format, citation style, a database or genome build they always use), a convention "
    "of their project or lab (units, species, naming, thresholds), or a correction they made to the assistant. Do not record facts about this "
    "one answer, anything found in search results, or things the assistant said. Write each fact as one short sentence, in the language the user "
    "wrote in. Reply with only a JSON array such as [{\"text\": \"...\", \"category\": \"Preference\"}], or [] when nothing qualifies."
)


def parse_candidates(raw: str) -> list[dict[str, str]]:
    """The suggestions in a model reply: a JSON array of {text, category}. Anything unreadable gives none."""
    m = re.search(r"\[.*\]", str(raw or ""), re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for c in data if isinstance(data, list) else []:
        if isinstance(c, str):
            c = {"text": c}
        if not isinstance(c, dict):
            continue
        text = str(c.get("text") or "").strip()
        if 8 <= len(text) <= MAX_CHARS:
            out.append({"text": text, "category": str(c.get("category") or DEFAULT_CATEGORY).strip()[:40] or DEFAULT_CATEGORY})
        if len(out) >= LEARN_MAX:
            break
    return out


def learn(question: str, answer: str, project_id: str | None, ask: Callable[[str, str], str]) -> list[dict[str, Any]]:
    """After a finished task, suggest lasting facts from the exchange. They are stored as proposals for the user to approve, never used
    unapproved. A short answer gives none, and a fact already remembered (in this scope or for all projects) is not suggested again."""
    if not str(question or "").strip() or len(str(answer or "").strip()) < 120:
        return []
    raw = ask(LEARN_SYSTEM, f"Question:\n{str(question)[:2000]}\n\nAnswer:\n{str(answer)[:3000]}")
    have = {(_norm(i["text"]), i["project_id"]) for i in _read()}
    added = []
    for c in parse_candidates(raw):
        key = _norm(c["text"])
        if (key, project_id or None) in have or (key, None) in have:
            continue
        have.add((key, project_id or None))
        added.append(add(c["text"], project_id, status=PROPOSED, category=c["category"], source="auto"))
    return added


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())
