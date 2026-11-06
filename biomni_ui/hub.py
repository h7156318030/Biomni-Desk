"""The community hub: one place to search skills, tools, databases and software, in the way Hermes' skills hub works.

- An index (community_index.json) lists every skill found in the verified skill sources (GitHub repositories), with its name, description,
  where it comes from, its trust level and its licence. Search reads this file, so it does not call GitHub each time. `build_index` rebuilds it.
- The curated catalogue (community_catalog.json) adds the tools (MCP servers), reading lists and software that are shown for reference.
- Trust: a skill from a repository in TRUSTED_REPOS is "trusted"; every other skill is "community".
- Install: the skill's text is downloaded and scanned (community_guard). The install policy then decides; every attempt is written to the
  audit log (ui_data/community_audit.jsonl), including the verdict and whether it was forced.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from biomni_ui import community, community_guard
from biomni_ui import skills as skill_files

INDEX = Path(__file__).resolve().parent / "community_index.json"
AUDIT = Path(__file__).resolve().parent.parent / "ui_data" / "community_audit.jsonl"
TRUSTED_REPOS: set[str] = set()  # repositories whose skills count as "trusted". None of the life-science sources is listed yet.
_lock = threading.Lock()
_index: dict[str, Any] | None = None
_status: dict[str, Any] = {"state": "idle", "message": ""}


def _get_text(url: str, token: str | None = None) -> str:
    headers = {"User-Agent": "Biomni-Desk community library"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"The address answered {r.status_code}.")
    return r.text


def trust_of(repo: str) -> str:
    return "trusted" if repo in TRUSTED_REPOS else "community"


def _raw(e: dict[str, Any], path: str) -> str:
    return f"https://raw.githubusercontent.com/{e['repo']}/{e.get('branch', 'main')}/{path}"


def _row(e: dict[str, Any], path: str, text: str) -> dict[str, Any]:
    meta, _body = skill_files.parse(text)
    name = (meta.get("name") or meta.get("title") or "").strip() or (path.rsplit("/", 2)[-2] if "/" in path else e["id"])
    return {
        "id": f"{e['id']}:{path}",
        "kind": "skills",
        "name": name,
        "description": " ".join((meta.get("description") or "").split())[:400],
        "repo": e["repo"],
        "path": path,
        "url": community.blob_url(e, path),
        "source": e["name"],
        "trust": trust_of(e["repo"]),
        "license": e.get("license", ""),
        "archived": bool(e.get("archived")),
        "last_changed": e.get("last_changed", ""),
        "keywords": [e["repo"], *e.get("keywords", [])],
    }


def build_index(entries: list[dict[str, Any]] | None = None, fetch: Callable[..., Any] = community._get_json,
                fetch_text: Callable[..., str] = _get_text, workers: int = 8) -> dict[str, Any]:
    """Crawl every skill source in the catalogue and write the index. Rows for skills whose text cannot be read are skipped (and counted)."""
    sources = [e for e in (entries if entries is not None else community.entries()) if e.get("kind") == "skills"]
    rows: list[dict[str, Any]] = []
    skipped = 0
    for e in sources:
        files = community.skill_files(e, None, fetch)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            def one(f: dict[str, str]) -> dict[str, Any] | None:
                try:
                    return _row(e, f["path"], fetch_text(_raw(e, f["path"])))
                except (ValueError, httpx.HTTPError):
                    return None
            for row in ex.map(one, files):
                if row is None:
                    skipped += 1
                else:
                    rows.append(row)
    data = {"built_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "count": len(rows), "skipped": skipped, "items": rows}
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(INDEX)
    global _index
    with _lock:
        _index = data
    return data


def index() -> dict[str, Any]:
    global _index
    with _lock:
        if _index is None:
            try:
                _index = json.loads(INDEX.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _index = {"built_on": "", "count": 0, "skipped": 0, "items": []}
        return _index


def status() -> dict[str, Any]:
    return dict(_status)


def start_refresh() -> bool:
    """Rebuild the index in the background (it calls GitHub). False when a rebuild is already running."""
    if _status.get("state") == "running":
        return False

    def run() -> None:
        _status.update(state="running", message="Reading the sources on GitHub…")
        try:
            data = build_index()
            _status.update(state="done", message=f"{data['count']} skills indexed ({data['skipped']} skipped).")
        except Exception as e:  # shown to the user; the old index stays in use
            _status.update(state="failed", message=f"{type(e).__name__}: {str(e)[:200]}")

    threading.Thread(target=run, name="hub-refresh", daemon=True).start()
    return True


def _matches(item: dict[str, Any], words: list[str]) -> bool:
    hay = " ".join([str(item.get("name", "")), str(item.get("description", "")), " ".join(item.get("keywords", [])),
                    str(item.get("source", ""))]).lower()
    return all(w in hay for w in words)


def search(q: str = "", kind: str | None = None, trust: str | None = None) -> list[dict[str, Any]]:
    """Index rows (skills) and curated entries (tools, lists), filtered by kind and trust, matching every word of the query."""
    words = [w for w in str(q or "").lower().split() if w]
    out: list[dict[str, Any]] = []
    if kind in (None, "", "skills"):
        out += [r for r in index().get("items", []) if (not trust or r.get("trust") == trust) and _matches(r, words)]
    if kind in (None, "", "tools", "lists", "databases", "software") and not trust:
        for e in community.entries():
            if kind and kind not in ("", None) and e.get("kind") != kind:
                continue
            if e.get("kind") == "skills":
                continue
            if _matches({**e, "source": e.get("repo", "")}, words):
                out.append({**e, "trust": "reference", "source": e.get("repo", "")})
    return out


def installed_urls() -> set[str]:
    """The blob addresses of the skills already in the library (from the source records kept at import)."""
    from biomni_ui import github_skills

    return {str(v.get("url") or "") for v in github_skills.sources().values()}


def audit(entry: dict[str, Any]) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.time(), **entry}, ensure_ascii=False) + "\n")


def inspect(url: str, fetch_text: Callable[[str], str] | None = None) -> dict[str, Any]:
    """Download one skill's text and scan it, without installing anything."""
    from biomni_ui import skill_import

    raw = skill_import.raw_address(url)
    text = (fetch_text or skill_import.fetch)(raw)
    res = community_guard.scan(text)
    return {"url": url, **res, "text": text[:4000]}


def install(url: str, force: bool = False, trust: str | None = None, fetch_text: Callable[[str], str] | None = None,
            store: Any = None) -> dict[str, Any]:
    """Scan, decide, and (when allowed) add the skill to the library. Raises PermissionError when the policy refuses."""
    from biomni_ui import github_skills, skill_import

    if store is None:
        raise ValueError("No skill library")
    repo = url.split("/blob/")[0].replace("https://github.com/", "")
    trust = trust or trust_of(repo)
    text = (fetch_text or skill_import.fetch)(skill_import.raw_address(url))
    res = community_guard.scan(text)
    allowed, reason = community_guard.decide(res["verdict"], trust, force)
    entry = {"url": url, "verdict": res["verdict"], "findings": len(res["findings"]), "trust": trust, "forced": bool(force and res["verdict"] == "caution"),
             "allowed": allowed, "reason": reason}
    if not allowed:
        audit({**entry, "result": "blocked"})
        raise PermissionError(json.dumps({"reason": reason, **res}, ensure_ascii=False))
    token = github_skills.get_token()
    skill = skill_import.import_skill(store, url, fetcher=lambda raw: text, token=token)
    audit({**entry, "result": "installed", "skill": skill.get("id")})
    return {"skill": skill, **res, "reason": reason}
