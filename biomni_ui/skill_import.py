"""Import a skill from a web address: a raw Markdown file, or a GitHub file page (turned into its raw address).

The skill is read once and saved as one of the user's own skills. Only https addresses are accepted, the file must be small,
and it must have a front matter block with a title and a body, the same format the skill editor writes. The imported text
goes into the agent's prompt when the skill is used, so import only skills you trust. The source address is kept at the
end of the body.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx

from biomni_ui import skills as skill_files

MAX_BYTES = 200_000
TIMEOUT_SECONDS = 15
_GITHUB_FILE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/(.+)$")


def raw_address(url: str) -> str:
    """The address to download: GitHub file pages become raw.githubusercontent.com addresses; other https addresses are used as they are."""
    url = (url or "").strip()
    if not url.startswith("https://"):
        raise ValueError("Only https:// addresses can be imported.")
    m = _GITHUB_FILE.match(url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return url


def fetch(raw: str) -> str:
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(raw, headers={"User-Agent": "Biomni-Desk skill import"})
    if response.status_code != 200:
        raise ValueError(f"The address answered {response.status_code}. Check that it links to the raw Markdown file.")
    if len(response.content) > MAX_BYTES:
        raise ValueError("The file is larger than 200 KB. A skill should be a short run-book.")
    return response.text


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:48].strip("-")
    return s or "imported-skill"


def import_skill(store: skill_files.SkillStore, url: str, fetcher: Callable[[str], str] = fetch, token: str | None = None,
                 commit_lookup: Callable[..., str | None] | None = None) -> dict[str, Any]:
    """Download, check and save one skill. Raises ValueError for bad input and FileExistsError when the name is taken.
    A GitHub file is downloaded with the stored token when there is one (private repositories), and its commit is recorded so
    that later updates can be checked (see github_skills.py)."""
    from biomni_ui import github_skills

    parsed = github_skills.parse_blob(url)
    if parsed and token:
        text = github_skills.fetch_text(*parsed, token)
    else:
        text = fetcher(raw_address(url))
    meta, body = skill_files.parse(text)
    if not meta.get("title", "").strip() and meta.get("name", "").strip():  # community skills (SKILL.md) name the skill with "name"
        meta["title"] = meta["name"].strip()
    if not meta.get("title", "").strip():
        raise ValueError("The file needs a front matter block at the top, with at least a title line between --- lines.")
    if not body.strip():
        raise ValueError("The file has no body after the front matter.")
    skill_id = slug(meta["title"])
    if store.get(skill_id) or (skill_files.BUILTIN_DIR / f"{skill_id}.md").is_file():
        raise FileExistsError(f"A skill named {skill_id} already exists. Rename the title or remove the old one first.")
    body = body.rstrip() + f"\n\n_Imported from {url.strip()}_"
    saved = store.save(skill_id, {k: meta.get(k, "") for k in skill_files.FIELDS}, body)
    if parsed:
        commit = None
        try:
            commit = (commit_lookup or github_skills.latest_commit)(*parsed, token)
        except Exception:  # no commit to remember is not a reason to refuse the import; updates then compare the content
            commit = None
        github_skills.record(skill_id, url.strip(), commit)
    return saved
