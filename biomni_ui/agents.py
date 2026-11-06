"""Agent profiles: a saved way of working that a task can use, in the spirit of Hermes profiles.

A profile sets, for the tasks that use it:
- the model (any saved model entry; empty means the model in use in Settings),
- the reasoning effort (empty means the model's default),
- the working mode (plan, ask or auto),
- which optional tools are off (web search, sub-agents, memory suggestions, questions to the user),
- the skills it always carries, and extra instructions.

Projects can also switch off tools for every task in them (see prefs.clean_project_settings: tools_off).
A profile never changes the global settings. Profiles are stored in ui_data/agents.json.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any

TOGGLEABLE_TOOLS = ("web_search", "delegate_task", "propose_memory", "ask_user")
MODES = ("plan", "ask", "auto")
MAX_PROFILES = 30
MAX_INSTRUCTIONS = 2000
MAX_SKILLS = 20
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def clean(data: dict[str, Any], model_ids: set[str], efforts: tuple[str, ...]) -> dict[str, Any]:
    """Validate and normalise one profile's editable fields. Raises ValueError with a message the page can show."""
    name = " ".join(str(data.get("name") or "").split())[:60]
    if not name:
        raise ValueError("A profile needs a name.")
    model_id = str(data.get("model_id") or "").strip() or None
    if model_id is not None and model_id not in model_ids:
        raise ValueError("The model chosen for this profile is no longer saved. Pick another one.")
    effort = str(data.get("effort") or "").strip() or None
    if effort is not None and effort not in efforts:
        raise ValueError(f"The reasoning effort must be one of: {', '.join(efforts)}.")
    mode = str(data.get("mode") or "ask")
    if mode not in MODES:
        raise ValueError("The mode must be plan, ask or auto.")
    off = [t for t in dict.fromkeys(str(x) for x in (data.get("tools_off") or [])) if t in TOGGLEABLE_TOOLS]
    skills = [str(s).strip() for s in (data.get("skills") or []) if str(s).strip()][:MAX_SKILLS]
    return {
        "name": name,
        "model_id": model_id,
        "effort": effort,
        "mode": mode,
        "tools_off": off,
        "skills": list(dict.fromkeys(skills)),
        "instructions": str(data.get("instructions") or "").strip()[:MAX_INSTRUCTIONS],
    }


class AgentStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return [p for p in json.loads(self.path.read_text(encoding="utf-8")).get("profiles", []) if isinstance(p, dict) and p.get("id")]
        except (OSError, ValueError):
            return []

    def _write(self, profiles: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, profile_id: str | None) -> dict[str, Any] | None:
        if not profile_id:
            return None
        return next((p for p in self.list() if p["id"] == profile_id), None)

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            profiles = self._read()
            if len(profiles) >= MAX_PROFILES:
                raise ValueError(f"At most {MAX_PROFILES} profiles can be saved.")
            profile = {"id": uuid.uuid4().hex[:10], **fields}
            profiles.append(profile)
            self._write(profiles)
        return profile

    def update(self, profile_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            profiles = self._read()
            hit = next((p for p in profiles if p["id"] == profile_id), None)
            if hit is None:
                return None
            hit.update(fields)
            self._write(profiles)
            return hit

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            profiles = self._read()
            kept = [p for p in profiles if p["id"] != profile_id]
            if len(kept) == len(profiles):
                return False
            self._write(kept)
            return True


def tools_off_for(profile: dict[str, Any] | None, project_settings: dict[str, Any] | None) -> set[str]:
    """Tools switched off for one task: the profile's choices plus the project's."""
    off = set((profile or {}).get("tools_off") or [])
    off |= set((project_settings or {}).get("tools_off") or [])
    return {t for t in off if t in TOGGLEABLE_TOOLS}
