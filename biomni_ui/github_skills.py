"""Skills from GitHub: private repositories (with a token you store on this computer), where each imported skill came from, and
checking for updates.

Imports still happen only when the user asks. Checking for updates is also on request: it looks at the latest commit that
touched each imported file, and lists the skills whose content changed. Nothing is replaced until the user selects it.

The token is kept in ui_data/credentials.json on this computer; the page only learns whether one is set, never its value.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from biomni_ui import skill_import
from biomni_ui import skills as skill_files

ROOT = Path(__file__).resolve().parent.parent / "ui_data"
CREDENTIALS = ROOT / "credentials.json"
SOURCES = ROOT / "skill_sources.json"
_lock = threading.Lock()
_BLOB = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")


# ---- the token ---------------------------------------------------------------------------------

def get_token() -> str | None:
    try:
        token = str(json.loads(CREDENTIALS.read_text(encoding="utf-8")).get("github_token") or "").strip()
    except (OSError, ValueError, AttributeError):
        return None
    return token or None


def set_token(token: str | None) -> bool:
    """Store the token, or remove it when empty. Returns whether a token is now set."""
    with _lock:
        CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
        clean = (token or "").strip()
        if clean:
            CREDENTIALS.write_text(json.dumps({"github_token": clean}), encoding="utf-8")
        elif CREDENTIALS.exists():
            CREDENTIALS.unlink()
    return bool(clean)


# ---- where a skill came from ---------------------------------------------------------------------

def parse_blob(url: str) -> tuple[str, str, str, str] | None:
    """(owner, repo, ref, path) for a GitHub file page such as https://github.com/o/r/blob/main/skills/x.md, else None.
    The branch or tag is the segment right after /blob/ (names with slashes are not supported)."""
    m = _BLOB.match((url or "").strip())
    return (m.group(1), m.group(2), m.group(3), m.group(4)) if m else None


def raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def _sources() -> dict[str, Any]:
    try:
        return json.loads(SOURCES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_sources(data: dict[str, Any]) -> None:
    SOURCES.parent.mkdir(parents=True, exist_ok=True)
    tmp = SOURCES.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SOURCES)


def record(skill_id: str, url: str, commit: str | None) -> None:
    parsed = parse_blob(url)
    if not parsed:
        return
    owner, repo, ref, path = parsed
    with _lock:
        data = _sources()
        data[skill_id] = {"url": url, "owner": owner, "repo": repo, "ref": ref, "path": path, "commit": commit, "imported": time.time()}
        _save_sources(data)


def forget(skill_id: str) -> None:
    with _lock:
        data = _sources()
        if data.pop(skill_id, None) is not None:
            _save_sources(data)


def sources() -> dict[str, Any]:
    return _sources()


# ---- talking to GitHub (injected in tests) ---------------------------------------------------------

def latest_commit(owner: str, repo: str, ref: str, path: str, token: str | None) -> str | None:
    """The sha of the latest commit that changed this file on this ref."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Biomni-Desk skill updates"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=15) as client:
        r = client.get(f"https://api.github.com/repos/{owner}/{repo}/commits", params={"path": path, "sha": ref, "per_page": 1}, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"GitHub answered {r.status_code} for {owner}/{repo}. Check the token and that the repository is reachable.")
    rows = r.json()
    return str(rows[0]["sha"]) if rows else None


def fetch_text(owner: str, repo: str, ref: str, path: str, token: str | None) -> str:
    headers = {"User-Agent": "Biomni-Desk skill updates"}
    if token:
        headers["Authorization"] = f"token {token}"
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        r = client.get(raw_url(owner, repo, ref, path), headers=headers)
    if r.status_code != 200:
        raise ValueError(f"GitHub answered {r.status_code} for {path}.")
    if len(r.content) > skill_import.MAX_BYTES:
        raise ValueError("The file is larger than 200 KB.")
    return r.text


# ---- checking and applying updates -------------------------------------------------------------------

def check_updates(store: skill_files.SkillStore, latest: Callable[..., str | None] = latest_commit,
                  fetch: Callable[..., str] = fetch_text, token: str | None = None) -> list[dict[str, Any]]:
    """The imported skills whose file changed since they were imported. Each row says what changed, nothing is written."""
    rows = []
    for skill_id, src in sources().items():
        current = store.get(skill_id)
        if current is None:
            continue
        newest = latest(src["owner"], src["repo"], src["ref"], src["path"], token)
        if src.get("commit") and newest == src.get("commit"):
            continue  # no newer commit on that file
        text = fetch(src["owner"], src["repo"], src["ref"], src["path"], token)
        meta, body = skill_files.parse(text)
        new_body = body.rstrip() + f"\n\n_Imported from {src['url']}_"
        changed = (meta.get("title", "").strip() != current.get("title", "").strip()) or (new_body.strip() != current.get("body", "").strip())
        rows.append({"skill_id": skill_id, "title": current.get("title", skill_id), "current_commit": src.get("commit"), "latest_commit": newest,
                     "changed": changed})
    return rows


def apply_updates(store: skill_files.SkillStore, skill_ids: list[str], latest: Callable[..., str | None] = latest_commit,
                  fetch: Callable[..., str] = fetch_text, token: str | None = None) -> list[str]:
    """Replace the selected skills with their latest versions and record the new commit. Returns the ids updated."""
    done = []
    for skill_id in skill_ids:
        src = sources().get(skill_id)
        if not src or store.get(skill_id) is None:
            continue
        text = fetch(src["owner"], src["repo"], src["ref"], src["path"], token)
        meta, body = skill_files.parse(text)
        if not meta.get("title", "").strip() or not body.strip():
            raise ValueError(f"The new version of {skill_id} has no title or body; it was not applied.")
        newest = latest(src["owner"], src["repo"], src["ref"], src["path"], token)
        store.save(skill_id, {k: meta.get(k, "") for k in skill_files.FIELDS}, body.rstrip() + f"\n\n_Imported from {src['url']}_")
        record(skill_id, src["url"], newest)
        done.append(skill_id)
    return done
