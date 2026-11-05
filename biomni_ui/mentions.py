"""`@` mentions: let the user point the agent at a specific skill, tool, dataset or file.

Candidates are searched here; the chosen ones are turned into plain instructions appended to the task, so the
agent receives exactly what was picked instead of having to guess from the question.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from biomni_ui import files
from biomni_ui.skills import SkillStore, render_for_agent

KINDS = ("skill", "tool", "data", "file")
MAX_RESULTS = 40
MAX_PER_KIND = 12  # per kind: skills, tools, data and files each keep a share of the list
MAX_FILES = 400


def _match(q: str, *texts: str) -> bool:
    q = q.strip().lower()
    return not q or any(q in (t or "").lower() for t in texts)


SKIP_DIRS = {".venv", "node_modules", ".next", "__pycache__", ".git", "ui_data", "biomni", "web", "biomni_ui",
             "skills", "biomni_lite.egg-info", "scripts"}
MAX_DEPTH = 3


def _workspace_files(roots: list[Path], q: str) -> list[dict[str, Any]]:
    """Walk the workspace without ever descending into heavy directories (a plain rglob would read all of .venv)."""
    out: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        base_depth = len(root.parts)
        scanned = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
            if len(Path(dirpath).parts) - base_depth >= MAX_DEPTH:
                dirnames[:] = []
            for name in sorted(filenames):
                scanned += 1
                if scanned > MAX_FILES:
                    break
                p = Path(dirpath) / name
                if p.suffix.lower() in files.ALLOWED_EXT and _match(q, name):
                    real = p.resolve()
                    if real not in seen:
                        seen.add(real)
                        out.append({"kind": "file", "id": str(real), "label": name, "hint": str(real.parent)})
            if scanned > MAX_FILES:
                break
    return out


def search(q: str, *, skills: SkillStore, tools: list[dict], data_lake: dict[str, str], roots: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in skills.list():
        if s["enabled"] and _match(q, s["title"], s["id"], s["description"]):
            out.append({"kind": "skill", "id": s["id"], "label": s["title"], "hint": s["description"]})
    for t in tools:
        name = t.get("name", "")
        if _match(q, name, t.get("description", "")):
            out.append({"kind": "tool", "id": name, "label": name, "hint": (t.get("description") or "")[:90]})
    for name, desc in data_lake.items():
        if _match(q, name, desc):
            out.append({"kind": "data", "id": name, "label": name, "hint": (desc or "")[:90]})
    out.extend(_workspace_files(roots, q))
    # Prefix matches first inside each kind, then keep the kind order skill > file > data > tool.
    order = {"skill": 0, "file": 1, "data": 2, "tool": 3}
    ql = q.strip().lower()
    out.sort(key=lambda m: (order[m["kind"]], not m["label"].lower().startswith(ql), m["label"].lower()))
    # Each kind gets its own share, so a long skill list cannot push tools, data and files out of the answer.
    shown: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for m in out:
        if shown.get(m["kind"], 0) < MAX_PER_KIND:
            kept.append(m)
            shown[m["kind"]] = shown.get(m["kind"], 0) + 1
    return kept[:MAX_RESULTS]


def to_prompt(mentions: list[dict[str, str]], *, skills: SkillStore, tool_names: set[str], data_names: set[str],
              roots: list[Path]) -> str:
    """Turn the picked mentions into instructions. Unknown or unsafe picks are skipped, never trusted."""
    lines: list[str] = []
    for m in mentions:
        kind, ident = m.get("kind"), m.get("id", "")
        if kind == "skill":
            s = skills.get(ident)
            if s:
                meta = {k: s[k] for k in ("title", "when_to_use", "avoid", "uses", "chain")}
                lines.append("The user asked you to follow the skill below; carry out its steps:\n" + render_for_agent(meta, s["body"]))
        elif kind == "tool" and ident in tool_names:
            lines.append(f"The user asked you to prefer the tool `{ident}`.")
        elif kind == "data" and ident in data_names:
            lines.append(f"The user asked you to use the data lake file `{ident}` (if it is not local, download it from Zenodo as instructed).")
        elif kind == "file":
            real = files.resolve(ident, roots)
            if real:
                lines.append(f"The user referred to the file: {real} (read it and use it).")
    return "\n\n".join(lines)
