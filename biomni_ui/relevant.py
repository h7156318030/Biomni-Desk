"""The Biomni functions and skills that a question calls for, listed in the task's instructions (the way the official A1 lists its
function dictionary and know-how for each task).

Chosen on this machine by keyword overlap (English words and the Chinese terms in agent_retrieval), so it costs no model call and adds a
few hundred characters per task. Only functions whose status is usable ("available" or "conditional") are offered. The model still reaches the rest
through find_tools and the full skill manuals through use_skill.

A function is offered when at least MIN_HITS of the question's words are in its name, module or description, and a word that most
functions share (cell, gene, data) does not count as a hit. One word, even in a name (rna, structure), is not a reason.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

from biomni_ui import skill_find
from biomni_ui.agent_retrieval import _tokens, query_tokens

TOP_FUNCTIONS = 6
TOP_SKILLS = 2
USABLE = ("available", "conditional")
MIN_HITS = 2  # words of the question that a function must share with it
GENERIC_SHARE = 0.08  # a word in more than this share of the usable functions is not a hit (cell, gene, data)
GENERIC_MIN = 3  # ...and only when more than this many functions share it
SWITCH = Path(__file__).resolve().parent.parent / "ui_data" / "relevant_switch.txt"


def enabled() -> bool:
    """On by default. Off when BIOMNI_UI_RELEVANT=0, or when ui_data/relevant_switch.txt says 0 (read per task: no restart)."""
    if os.environ.get("BIOMNI_UI_RELEVANT", "1") == "0":
        return False
    try:
        return SWITCH.read_text(encoding="utf-8").strip() != "0"
    except OSError:
        return True


def _params(required: str) -> list[str]:
    return re.findall(r"\('(\w+)'", str(required or ""))


def _words(f: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    name_w = _tokens(str(f.get("name", "")).replace("_", " "))
    mod_w = _tokens(str(f.get("import", "")).split(".")[-1])
    desc_w = _tokens(str(f.get("description", "")))
    return name_w, mod_w, desc_w


def functions_for(question: str, catalog: list[dict[str, Any]], k: int = TOP_FUNCTIONS) -> list[dict[str, Any]]:
    q = query_tokens(question)
    if not q:
        return []
    words = [(f, _words(f)) for f in catalog if f.get("status") in USABLE]
    n = len(words)
    if not n:
        return []
    df = {t: sum(1 for _, (a, b, c) in words if t in a or t in b or t in c) for t in q}
    generic = {t for t in q if df[t] > max(GENERIC_SHARE * n, GENERIC_MIN)}  # a small catalogue has no generic words
    scored: list[tuple[float, dict[str, Any]]] = []
    for f, (name_w, mod_w, desc_w) in words:
        hits = [t for t in q if t not in generic and (t in name_w or t in mod_w or t in desc_w)]
        if len(hits) < MIN_HITS:
            continue
        score = 0.0
        for t in hits:
            weight = 3 if t in name_w else 2 if t in mod_w else 1
            score += weight * math.log((n + 1) / (df[t] + 0.5))  # a rarer word counts for more
        scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:k]]


def skills_for(question: str, skills: list[dict[str, Any]], k: int = TOP_SKILLS) -> list[dict[str, Any]]:
    return [s for _, s in skill_find.scored(question, skills)[:k]]


def block(question: str, catalog: list[dict[str, Any]], skills: list[dict[str, Any]]) -> str:
    """The text for the task's instructions: the functions and skills this question calls for, or nothing when there are none."""
    funcs = functions_for(question, catalog)
    picked = skills_for(question, skills)
    if not funcs and not picked:
        return ""
    lines: list[str] = []
    if funcs:
        lines.append("## Biomni functions relevant to this question (call them directly first: import, assign the result and print it)")
        for f in funcs:
            params = _params(f.get("required", ""))
            desc = " ".join(str(f.get("description", "")).split())[:140]
            lines.append(f"- {f['name']}: {desc}")
            lines.append(f"  from {f['import']} import {f['name']}; required parameters: {', '.join(params) or 'none'}")
    if picked:
        lines.append("## Skills relevant to this question (load the full text by number with use_skill)")
        for s in picked:
            when = " ".join(str(s.get("when_to_use") or s.get("description") or "").split())[:120]
            lines.append(f"- {s['id']}: {' '.join(str(s.get('title') or s['id']).split())[:50]}. Use when: {when}")
    return "\n".join(lines)
