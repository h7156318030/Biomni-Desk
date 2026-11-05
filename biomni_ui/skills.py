"""Skill packages: Markdown run-books the agent can retrieve and follow.

A skill is one .md file with a small front matter block:

    ---
    title: Literature search and review
    description: One line on what it is for
    category: Literature
    when_to_use: When to use it
    avoid: When not to use it, and what to use instead
    uses: query_pubmed, query_scholar
    chain: Upstream skills or outputs
    ---
    Body: steps, input and output conventions, cautions (Markdown)

Built-in skills ship in `biomni_ui/builtin_skills/` (read-only). The user's own skills live in `<repo>/skills/`.
Each enabled skill is registered with the agent's know-how loader, so the existing tool/knowledge retriever
decides per task which ones to put in the prompt.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

BUILTIN_DIR = Path(__file__).parent / "builtin_skills"
FIELDS = ("title", "description", "category", "when_to_use", "avoid", "uses", "chain")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
PREFIX = "skill_"


def parse(text: str) -> tuple[dict[str, str], str]:
    """Split a skill file into (front matter fields, markdown body)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


def dump(meta: dict[str, str], body: str) -> str:
    head = "\n".join(f"{k}: {' '.join(str(meta.get(k, '')).split())}" for k in FIELDS if meta.get(k))
    return f"---\n{head}\n---\n{body.strip()}\n"


def render_for_agent(meta: dict[str, str], body: str) -> str:
    """The text that goes into the agent prompt when this skill is retrieved."""
    lines = [f"# {meta.get('title', 'Skill')}"]
    if meta.get("when_to_use"):
        lines.append(f"When to use: {meta['when_to_use']}")
    if meta.get("avoid"):
        lines.append(f"Not for: {meta['avoid']}")
    if meta.get("uses"):
        lines.append(f"Depends on: {meta['uses']}")
    if meta.get("chain"):
        lines.append(f"Upstream and downstream: {meta['chain']}")
    return "\n".join(lines) + "\n\n" + body


class SkillStore:
    def __init__(self, user_dir: Path, state_file: Path):
        self.user_dir = user_dir
        self.state_file = state_file
        self._lock = threading.Lock()
        user_dir.mkdir(parents=True, exist_ok=True)

    # -- enabled state --------------------------------------------------------------------
    def _disabled(self) -> set[str]:
        try:
            return set(json.loads(self.state_file.read_text(encoding="utf-8")).get("disabled", []))
        except (OSError, ValueError):
            return set()

    def set_enabled(self, skill_id: str, enabled: bool) -> None:
        with self._lock:
            disabled = self._disabled()
            (disabled.discard if enabled else disabled.add)(skill_id)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"disabled": sorted(disabled)}), encoding="utf-8")

    # -- reading --------------------------------------------------------------------------
    def _path(self, skill_id: str) -> tuple[Path, str] | None:
        if not ID_RE.match(skill_id):
            return None
        for root, source in ((self.user_dir, "mine"), (BUILTIN_DIR, "builtin")):
            p = root / f"{skill_id}.md"
            if p.is_file():
                return p, source
        return None

    def get(self, skill_id: str) -> dict[str, Any] | None:
        found = self._path(skill_id)
        if not found:
            return None
        path, source = found
        meta, body = parse(path.read_text(encoding="utf-8"))
        return {
            "id": skill_id,
            "source": source,
            "enabled": skill_id not in self._disabled(),
            "title": meta.get("title") or skill_id,
            **{k: meta.get(k, "") for k in FIELDS if k != "title"},
            "body": body,
        }

    def list(self) -> list[dict[str, Any]]:
        ids: dict[str, None] = {}
        for root in (self.user_dir, BUILTIN_DIR):
            for p in sorted(root.glob("*.md")) if root.exists() else []:
                ids.setdefault(p.stem)
        out = [s for s in (self.get(i) for i in ids) if s]
        for s in out:
            s["body"] = ""  # list view stays light
        return out

    # -- writing (user skills only) -------------------------------------------------------
    def save(self, skill_id: str, meta: dict[str, str], body: str) -> dict[str, Any]:
        if not ID_RE.match(skill_id):
            raise ValueError("The skill ID may only contain lowercase letters, digits, underscores and hyphens, and must be at most 48 characters")
        if (BUILTIN_DIR / f"{skill_id}.md").is_file():
            raise ValueError("This ID is already used by a built-in skill. Choose another.")
        if not meta.get("title", "").strip():
            raise ValueError("The title cannot be empty")
        if not body.strip():
            raise ValueError("The body cannot be empty")
        (self.user_dir / f"{skill_id}.md").write_text(dump(meta, body), encoding="utf-8")
        return self.get(skill_id)  # type: ignore[return-value]

    def delete(self, skill_id: str) -> bool:
        p = self.user_dir / f"{skill_id}.md"
        if ID_RE.match(skill_id) and p.is_file():
            p.unlink()
            return True
        return False

    # -- agent integration ----------------------------------------------------------------
    def sync_agent(self, agent) -> int:
        """Replace the skill documents in the agent's know-how loader with the enabled skills."""
        loader = agent.know_how_loader
        for doc_id in [d for d in loader.documents if d.startswith(PREFIX)]:
            loader.remove_document(doc_id)
        n = 0
        for item in self.list():
            if not item["enabled"]:
                continue
            full = self.get(item["id"])
            meta = {k: full[k] for k in FIELDS}
            text = render_for_agent(meta, full["body"])
            doc_id = PREFIX + item["id"]
            loader.add_custom_document(
                doc_id, full["title"], full["description"] or full["when_to_use"], text, {"source": "skill"}
            )
            # The retrieval path reads this key; add_custom_document does not set it.
            loader.documents[doc_id]["content_without_metadata"] = text
            n += 1
        return n
