"""Who the user is and how they like to work: stored locally, and turned into a short briefing for every new task.

Nothing here is decoration: each field ends up in the text the agent receives (see `briefing`), or changes what the
page does (theme, automatic review).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

# Research areas saved by earlier versions in Chinese map to the English names.
LEGACY_AREAS = {"基因组学": "Genomics", "转录组学": "Transcriptomics", "蛋白质组学": "Proteomics", "结构生物学": "Structural biology", "药物发现": "Drug discovery", "CRISPR / 基因编辑": "CRISPR / gene editing", "人类遗传学": "Human genetics", "免疫学": "Immunology", "神经科学": "Neuroscience", "代谢组学": "Metabolomics", "单细胞": "Single-cell", "临床研究": "Clinical research", "生物信息学": "Bioinformatics", "其他": "Other"}
AREAS = [
    "Genomics", "Transcriptomics", "Proteomics", "Structural biology", "Drug discovery", "CRISPR / gene editing", "Human genetics",
    "Immunology", "Neuroscience", "Metabolomics", "Single-cell", "Clinical research", "Bioinformatics", "Other",
]
LANGUAGES = ("any", "python", "r")
IMAGE_FORMATS = ("any", "png", "svg")
STYLES = ("classic", "modern")
APPEARANCES = ("auto", "light", "dark")

MAX_INSTRUCTIONS = 20
MAX_INSTRUCTION_CHARS = 500
MAX_CONTEXT_CHARS = 4000

DEFAULTS: dict[str, Any] = {
    "profile": {
        "first_name": "", "last_name": "", "institution": "", "position": "",
        "scholar": "", "website": "", "orcid": "", "areas": [],
    },
    "prefs": {
        "language": "any", "image_format": "any", "style": "classic", "appearance": "auto",
        "instructions": [], "use_last_results": True, "auto_review": False,
    },
}

_TEXT_LIMITS = {"first_name": 40, "last_name": 40, "institution": 120, "position": 80, "scholar": 300, "website": 300, "orcid": 40}


def _text(v: Any, limit: int) -> str:
    return " ".join(str(v or "").split())[:limit]


def _lines(v: Any, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        t = " ".join(str(x or "").split())[:max_chars]
        if t and t not in out:
            out.append(t)
    return out[:max_items]


def clean(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only known fields with sane values; anything else in `data` is dropped."""
    profile_in = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    prefs_in = data.get("prefs") if isinstance(data.get("prefs"), dict) else {}
    profile = {k: _text(profile_in.get(k), n) for k, n in _TEXT_LIMITS.items()}
    profile["areas"] = [LEGACY_AREAS.get(a, a) for a in _lines(profile_in.get("areas"), len(AREAS) + len(LEGACY_AREAS), 40)]
    profile["areas"] = [a for a in profile["areas"] if a in AREAS]

    def choice(key: str, allowed: tuple[str, ...]) -> str:
        v = str(prefs_in.get(key, DEFAULTS["prefs"][key])).lower()
        return v if v in allowed else DEFAULTS["prefs"][key]

    prefs = {
        "language": choice("language", LANGUAGES),
        "image_format": choice("image_format", IMAGE_FORMATS),
        "style": choice("style", STYLES),
        "appearance": choice("appearance", APPEARANCES),
        "instructions": _lines(prefs_in.get("instructions"), MAX_INSTRUCTIONS, MAX_INSTRUCTION_CHARS),
        "use_last_results": bool(prefs_in.get("use_last_results", DEFAULTS["prefs"]["use_last_results"])),
        "auto_review": bool(prefs_in.get("auto_review", DEFAULTS["prefs"]["auto_review"])),
    }
    return {"profile": profile, "prefs": prefs}


def clean_project_settings(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": str(data.get("context") or "").strip()[:MAX_CONTEXT_CHARS],
        "instructions": _lines(data.get("instructions"), MAX_INSTRUCTIONS, MAX_INSTRUCTION_CHARS),
        "skills": _lines(data.get("skills"), 20, 60),
        "files": _lines(data.get("files"), 20, 200),  # upload names the project's tasks can read
        "tools_off": [t for t in dict.fromkeys(str(x) for x in (data.get("tools_off") or [])) if t in _toggleable()][:10],
        "memory_on": bool(data.get("memory_on", True)),  # off: nothing remembered is used in this project's tasks
    }


def _toggleable() -> tuple[str, ...]:
    from biomni_ui import agents

    return agents.TOGGLEABLE_TOOLS


class PrefsStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raw = {}
        return clean(raw if isinstance(raw, dict) else {})

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        value = clean(data)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value


def briefing(prefs: dict[str, Any], project: dict[str, Any] | None = None, recent_files: list[str] | None = None) -> str:
    """The background and preferences the agent should keep in mind, as plain text ("" when there is nothing to say)."""
    p, f = prefs["profile"], prefs["prefs"]
    lines: list[str] = []

    who = []
    name = f"{p['last_name']}{p['first_name']}".strip()
    if name:
        who.append(f"Name {name}")
    for label, key in (("Institution", "institution"), ("Position", "position"), ("ORCID", "orcid"), ("Google Scholar", "scholar"), ("Website", "website")):
        if p[key]:
            who.append(f"{label} {p[key]}")
    if p["areas"]:
        who.append("Research areas " + ", ".join(p["areas"]))
    if who:
        lines.append("User background: " + "; ".join(who) + ". (For example, when looking up an author's papers, this helps tell apart people with the same name.)")

    habits = []
    if f["language"] != "any":
        habits.append(f"When writing code, prefer {'Python' if f['language'] == 'python' else 'R'}")
    if f["image_format"] != "any":
        habits.append(f"When saving images, prefer {f['image_format'].upper()} format")
    if habits:
        lines.append("Working habits: " + "; ".join(habits) + ".")

    if project and project.get("context"):
        lines.append("Project background: " + project["context"])

    rules = [*f["instructions"], *((project or {}).get("instructions") or [])]
    if rules:
        lines.append("Standing instructions (follow them, including requirements on answer format and content):\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1)))

    if f["use_last_results"] and recent_files:
        lines.append("Files this project produced earlier: " + ", ".join(recent_files[:8]) + ". Read them only when the user explicitly refers to “the last result”, “the earlier files” or “continue”; "
                     "For a new question, do not read them or treat them as evidence; query again each time.")

    if not lines:
        return ""
    return "The following is background and preferences the user set in Settings. Use the background only when it is relevant to the question, and do not repeat it in the answer. Standing instructions must be followed:\n" + "\n".join(lines)
