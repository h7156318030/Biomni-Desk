"""Ranking for find_skills, and for the skills offered in a task's instructions.

A query matches a skill when one of its words appears in the skill's id (weight 3), title (2) or other notes (1). Matching is on whole
words: a hyphenated pair counts as one word too (RNA-seq also matches rnaseq, and so matches scrnaseq in an id), and the English and
Chinese terms of agent_retrieval are expanded both ways (single cell matches 单细胞). A word that most skills share (cell, data,
analysis) counts for little, so a specific word decides the order.
"""

from __future__ import annotations

import math
import re
from typing import Any

from biomni_ui.agent_retrieval import _CN_EN

STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "how", "what", "which", "use", "using", "should", "does", "into",
    "about", "of", "to", "in", "on", "a", "an", "is", "be", "by", "or", "do",
    # generic words of this field: nearly every biology skill has them, so they only add noise to the ranking
    "cell", "cells", "type", "types", "workflow", "analysis", "data", "method", "methods", "study", "pipeline",
}
NOTE_FIELDS = ("description", "when_to_use", "uses", "category")


def _en_to_cn() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for cn, ens in _CN_EN.items():
        for en in ens:
            out.setdefault(en.lower(), []).append(cn)
    return out


_EN_CN = _en_to_cn()


def _compact(text: str) -> str:
    """Lower case, with everything but letters, digits and Chinese characters removed: single-cell and singlecell are the same."""
    return re.sub(r"[^a-z0-9一-鿿]", "", text.lower())


def terms(query: str) -> set[str]:
    """The words of a query, in compact form: English words, hyphenated pairs as one word, Chinese runs and their character pairs,
    and the Chinese words for the English terms it contains."""
    q = str(query or "").lower()
    out: set[str] = set()
    compounds = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)+", q)
    for m in compounds:  # RNA-seq is one term (rnaseq), not three (rna, seq and rnaseq would count the same idea three times)
        out.add(_compact(m))
        out.update(_EN_CN.get(m.replace("_", "-"), []))
    rest = re.sub(r"[a-z0-9]+(?:[-_][a-z0-9]+)+", " ", q)
    words = re.findall(r"[a-z0-9]+", rest)
    for w in words:
        if len(w) < 2 or w in STOP:  # a generic word (cell, type) does not stand for its Chinese word either
            continue
        out.add(w)
        out.update(_EN_CN.get(w, []))
    for a, b in zip(words, words[1:]):
        out.update(_EN_CN.get(f"{a} {b}", []))
    for run in re.findall(r"[一-鿿]+", q):
        if len(run) >= 2:
            out.add(run)
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return {t for t in (_compact(x) for x in out) if t}


def _fields(item: dict[str, Any]) -> dict[str, str]:
    notes = " ".join(str(item.get(k) or "") for k in NOTE_FIELDS)
    return {"id": _compact(str(item.get("id") or "")), "title": _compact(str(item.get("title") or "")), "notes": _compact(notes)}


WEIGHT = {"id": 3, "title": 2, "notes": 1}


def scored(query: str, items: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any]]]:
    """(score, skill) for every enabled skill the query shares a word with, best first. A score is above zero only for a match."""
    enabled = [i for i in items if i.get("enabled", True)]
    q = terms(query)
    if not q or not enabled:
        return []
    docs = [(i, _fields(i)) for i in enabled]
    n = len(docs)
    df = {t: sum(1 for _, f in docs if any(t in f[name] for name in WEIGHT)) for t in q}
    out: list[tuple[float, dict[str, Any]]] = []
    for item, fields in docs:
        total = 0.0
        for t in q:
            best = max((WEIGHT[name] for name in WEIGHT if t in fields[name]), default=0)
            if best:
                total += best * math.log((n + 1) / (df[t] + 0.5))  # a word in every skill adds almost nothing
        if total > 0:
            out.append((total, item))
    out.sort(key=lambda x: -x[0])
    return out
