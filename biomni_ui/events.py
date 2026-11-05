"""Turn the agent's tagged text messages into structured UI events.

The upstream Gradio UI parses `<execute>/<observation>/<solution>` with regexes inline in a
generator. Here the same parsing is a pure function so it can be tested and reused by any front end.

Event shapes (all dicts, JSON serialisable):
    {"type": "plan",        "steps": [{"text": str, "status": "todo"|"done"|"failed"}]}
    {"type": "reasoning",   "text": str}
    {"type": "code",        "language": "python"|"r"|"bash", "code": str}
    {"type": "observation", "text": str, "files": [str]}
    {"type": "answer",      "text": str}
"""

from __future__ import annotations

import re

_PLAN_LINE = re.compile(r"^\s*(\d+)\.\s*\[(?P<mark>[ ✓✗xX])\]\s*(?P<text>.+?)\s*$")
_PLAN_MARK = re.compile(r"(\d+)\.[ \t]*\[([ ✓✗xX])\][ \t]*")
_STATUS = {" ": "todo", "✓": "done", "x": "done", "X": "done", "✗": "failed"}
_TAGS = ("<execute>", "<solution>", "<observation>")
_FILE_EXT = r"(?:png|jpg|jpeg|gif|bmp|webp|pdf|svg|csv|tsv|html|pptx|xlsx|docx|mp4|webm|mov)"
_FILE_RE = re.compile(rf"(\S+?\.{_FILE_EXT})\b", re.IGNORECASE)


def parse_plan(text: str) -> list[dict] | None:
    """Return the checklist found in `text`, or None when there is none."""
    marks = list(_PLAN_MARK.finditer(text))
    if not marks:
        return None
    parsed: list[tuple[int, str, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        lines = text[m.end():end].splitlines()
        parsed.append((int(m.group(1)), m.group(2), lines[0].strip() if lines else ""))
    # Models sometimes restate the whole checklist (even several times on one line): keep the last full run from "1.".
    start = max((i for i, p in enumerate(parsed) if p[0] == 1), default=0)
    steps, prev = [], 0
    for n, mark, body in parsed[start:]:
        if n <= prev:
            break
        prev = n
        if body:
            steps.append({"text": body, "status": _STATUS[mark]})
    return steps or None


_PLAN_ITEM_ANYWHERE = re.compile(r"\d+\.[ \t]*\[[ ✓✗xX]\][^\n]*")


def _strip_plan_lines(text: str) -> str:
    """Remove the checklist from a message. The model often restates it two or three times, sometimes glued to the end of the
    previous sentence, so items are removed wherever they start, not only at the start of a line."""
    lines = [ln for ln in text.splitlines() if not _PLAN_LINE.match(ln)]
    return re.sub(r"\n{3,}", "\n\n", _PLAN_ITEM_ANYWHERE.sub("", "\n".join(lines))).strip()


def _split_code(code: str) -> tuple[str, str]:
    code = code.strip()
    if code.startswith("#!R"):
        return "r", code[3:].strip()
    if code.startswith(("#!BASH", "#!CLI")):
        return "bash", re.sub(r"^#!BASH|^#!CLI", "", code, count=1).strip()
    return "python", code


def extract_files(observation: str) -> list[str]:
    """Candidate file paths mentioned in an observation (same filtering as the Gradio UI)."""
    out = []
    for raw in _FILE_RE.findall(observation):
        # Same filter as the Gradio UI: skip fragments of quoted/relative/diagnostic text.
        if raw.startswith(("Warning:", "Error:", "'", ".")):
            continue
        p = raw.strip("\"(),[]")
        if not p:
            continue
        if p not in out:
            out.append(p)
    return out


def message_to_events(content: str) -> list[dict]:
    """Parse one agent message into ordered events."""
    events: list[dict] = []

    positions = [content.find(t) for t in _TAGS if content.find(t) != -1]
    head = content[: min(positions)] if positions else content
    head = head.strip()

    plan = parse_plan(head)
    if plan:
        events.append({"type": "plan", "steps": plan})
        head = _strip_plan_lines(head)
    if head and positions:
        events.append({"type": "reasoning", "text": head})

    for m in re.finditer(r"<execute>(.*?)(?:</execute>|$)", content, re.DOTALL):
        language, code = _split_code(m.group(1))
        if code:
            events.append({"type": "code", "language": language, "code": code})

    m = re.search(r"<observation>(.*?)</observation>", content, re.DOTALL)
    if m:
        obs = m.group(1).strip()
        events.append({"type": "observation", "text": obs, "files": extract_files(obs)})

    m = re.search(r"<solution>(.*?)(?:</solution>|$)", content, re.DOTALL)
    if m:
        # The model often repeats its progress checklist at the top of the solution; the plan has its own panel.
        events.append({"type": "answer", "text": _strip_plan_lines(m.group(1)).strip()})

    return events
