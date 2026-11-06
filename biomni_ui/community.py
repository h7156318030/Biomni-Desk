"""The curated library of community skills, tools and reference lists (community_catalog.json).

Only the entries in that file can be browsed. For a skills entry the app lists the SKILL.md files in its repository (through the GitHub
tree API) and installs the ones the user picks, one by one, through the same import as "add a skill from a link". Only paths that appear
in that listing can be installed, so no other address gets in. Tools and lists are shown for reference only: this app does not run MCP
servers, and a list is not something to install."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx

CATALOG = Path(__file__).resolve().parent / "community_catalog.json"
KINDS = ("skills", "tools", "lists")
MAX_INSTALL = 50
CACHE_SECONDS = 3600
_lock = threading.Lock()
_catalog: dict[str, Any] | None = None
_tree_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}


def catalog() -> dict[str, Any]:
    """The catalogue file, read once. A missing or unreadable file reads as an empty list."""
    global _catalog
    with _lock:
        if _catalog is None:
            try:
                _catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _catalog = {"checked_on": "", "note": "", "entries": []}
        return _catalog


def entries() -> list[dict[str, Any]]:
    return list(catalog().get("entries", []))


def entry(entry_id: str) -> dict[str, Any] | None:
    return next((e for e in entries() if e.get("id") == entry_id), None)


def search(q: str = "", kind: str | None = None) -> list[dict[str, Any]]:
    """Entries of one kind (or all) whose name, description, keywords or repository contain every word of the query."""
    words = [w for w in str(q or "").lower().split() if w]
    out = []
    for e in entries():
        if kind and e.get("kind") != kind:
            continue
        hay = " ".join([str(e.get("name", "")), str(e.get("description", "")), str(e.get("repo", "")), " ".join(e.get("keywords", []))]).lower()
        if all(w in hay for w in words):
            out.append(e)
    return out


def blob_url(e: dict[str, Any], path: str) -> str:
    return f"https://github.com/{e['repo']}/blob/{e.get('branch', 'main')}/{path}"


def _get_json(url: str, token: str | None) -> Any:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Biomni-Desk community library"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"GitHub answered {r.status_code} for this repository. If it says the rate limit was reached, try again later or save a GitHub token in Settings.")
    return r.json()


def skill_files(e: dict[str, Any], token: str | None = None, fetch: Callable[..., Any] = _get_json) -> list[dict[str, str]]:
    """The SKILL.md files of a skills entry (under its prefix, outside its excluded folders), by path. Cached for an hour per repository."""
    if e.get("kind") != "skills":
        raise ValueError("This entry is not a skill collection.")
    key = e["repo"]
    cached = _tree_cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    tree = fetch(f"https://api.github.com/repos/{e['repo']}/git/trees/{e.get('branch', 'main')}?recursive=1", token)
    if tree.get("truncated"):
        raise ValueError("The repository is too large to list in one go. Browse it on GitHub instead.")
    prefix = e.get("skill_prefix", "")
    excluded = tuple(e.get("exclude_prefixes", []))
    out = []
    for node in tree.get("tree", []):
        path = node.get("path", "")
        if node.get("type") != "blob" or not path.endswith("SKILL.md") or not path.startswith(prefix):
            continue
        if excluded and path.startswith(excluded):
            continue
        folder = path.rsplit("/", 2)[-2] if "/" in path else e["id"]
        out.append({"path": path, "folder": folder})
    out.sort(key=lambda x: x["path"])
    _tree_cache[key] = (time.time(), out)
    return out


def install(e: dict[str, Any], paths: list[str], store: Any, token: str | None, importer: Callable[..., dict[str, Any]], fetch: Callable[..., Any] = _get_json) -> list[dict[str, Any]]:
    """Import the chosen skill files. Each path must be one of the listed files. Returns one result per path: the new skill, or why it was not added."""
    if e.get("kind") != "skills":
        raise ValueError("Only skill collections can be installed.")
    if not paths:
        raise ValueError("Choose at least one skill to add.")
    if len(paths) > MAX_INSTALL:
        raise ValueError(f"Add at most {MAX_INSTALL} skills at a time.")
    listed = {f["path"] for f in skill_files(e, token, fetch)}
    results = []
    for path in paths:
        if path not in listed:
            results.append({"path": path, "ok": False, "error": "Not in this repository's listing."})
            continue
        try:
            skill = importer(store, blob_url(e, path), token=token)
            results.append({"path": path, "ok": True, "id": skill.get("id"), "title": skill.get("title")})
        except FileExistsError as err:
            results.append({"path": path, "ok": False, "error": str(err)})
        except (ValueError, httpx.HTTPError) as err:
            results.append({"path": path, "ok": False, "error": str(err) or type(err).__name__})
    return results
