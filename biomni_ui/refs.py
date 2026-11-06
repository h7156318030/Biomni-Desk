"""Resolve citation identifiers (PMID, DOI, URL) into readable reference records.

The answer only carries identifiers; the reference list shows title, authors, journal and year. Lookups go to
PubMed (esummary), Crossref and, for plain web pages, the page's own <title>. Results are cached on disk, and
URL fetching is limited to public hosts so the agent's output can never make the server probe the local network.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

TIMEOUT = 12
MAX_ITEMS = 30
UA = "Biomni-Desk-workbench/0.1 (reference lookup; local use)"
PUBMED = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF = "https://api.crossref.org/works/"


def key_of(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def is_public_host(host: str) -> bool:
    """True only if every address the host resolves to is a public one."""
    if not host or host.lower() in ("localhost",):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return bool(infos)


def _get(url: str, **kw: Any) -> requests.Response:
    """GET with the system proxy first; academic sites sometimes fail through it, so retry directly once."""
    headers = {"User-Agent": UA, **kw.pop("headers", {})}
    try:
        return requests.get(url, timeout=TIMEOUT, headers=headers, **kw)
    except requests.RequestException:
        with requests.Session() as s:
            s.trust_env = False
            return s.get(url, timeout=TIMEOUT, headers=headers, **kw)


def _authors(names: list[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    return names[0] if len(names) == 1 else f"{names[0]} and others" if len(names) > 3 else ", ".join(names)


def parse_pubmed(data: dict[str, Any], pmids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    result = data.get("result", {})
    for pmid in pmids:
        rec = result.get(pmid)
        if not isinstance(rec, dict) or "error" in rec:
            continue
        doi = next((a["value"] for a in rec.get("articleids", []) if a.get("idtype") == "doi"), "")
        out[key_of("pmid", pmid)] = {
            "title": (rec.get("title") or "").rstrip("."),
            "authors": _authors([a.get("name", "") for a in rec.get("authors", [])]),
            "journal": rec.get("fulljournalname") or rec.get("source") or "",
            "year": (rec.get("pubdate") or "")[:4],
            "doi": doi,
            "kind": "paper",
        }
    return out


def parse_crossref(data: dict[str, Any]) -> dict[str, Any] | None:
    msg = data.get("message")
    if not isinstance(msg, dict):
        return None
    title = (msg.get("title") or [""])[0]
    authors = [" ".join(filter(None, [a.get("given", "")[:1], a.get("family", "")])) for a in msg.get("author", [])]
    issued = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
    return {
        "title": html.unescape(re.sub(r"<[^>]+>", "", title)),
        "authors": _authors(authors),
        "journal": (msg.get("container-title") or [""])[0],
        "year": str(issued or ""),
        "doi": msg.get("DOI", ""),
        "kind": "paper",
    }


def decode_page(raw: bytes, content_type: str = "") -> str:
    """Page bytes -> text. Chinese sites often send GBK with no (or a wrong) header charset; trust a declared charset, then the page's
    own <meta>, then a UTF-8 try, then detection, so a title never comes out as Latin-1 mojibake."""
    declared = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    meta = re.search(rb"<meta[^>]+charset=[\"']?\s*([\w-]+)", raw[:4096], re.I)
    names = [m.group(1).decode("ascii", "ignore") if isinstance(m.group(1), bytes) else m.group(1) for m in (meta,) if m]
    if declared:  # ISO-8859-1 is what servers claim when they say nothing: the page's own meta is better then
        names.insert(0 if declared.group(1).lower() not in ("iso-8859-1", "latin-1", "latin1") else len(names), declared.group(1))
    for name in names:
        if name.lower() in ("gb2312", "gbk"):
            name = "gb18030"
        try:
            return raw.decode(name)
        except (LookupError, UnicodeDecodeError):
            continue
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:  # most undeclared non-UTF-8 pages in this tool's use are Chinese GBK: take it when it decodes cleanly to mostly Chinese text
        text = raw.decode("gb18030")
        cjk = sum("一" <= c <= "鿿" for c in text)
        if cjk >= 0.15 * max(1, sum(not c.isspace() for c in text if ord(c) > 127 or c.isalpha())):
            return text
    except UnicodeDecodeError:
        pass
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:
        pass
    return raw.decode("gb18030", errors="replace")


def parse_title(page: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    return " ".join(html.unescape(m.group(1)).split())[:200] if m else ""


class RefResolver:
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self._lock = threading.Lock()
        try:
            self._cache: dict[str, dict[str, Any]] = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._cache = {}

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")

    def resolve(self, items: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
        items = items[:MAX_ITEMS]
        out: dict[str, dict[str, Any]] = {}
        want_pmid, want_doi, want_url = [], [], []
        for it in items:
            kind, ident = it.get("kind", ""), it.get("id", "")
            k = key_of(kind, ident)
            if k in self._cache:
                out[k] = self._cache[k]
            elif kind == "pmid" and re.fullmatch(r"\d{4,9}", ident):
                want_pmid.append(ident)
            elif kind == "doi" and re.fullmatch(r"10\.\d{4,9}/\S{1,200}", ident):
                want_doi.append(ident)
            elif kind == "url" and re.match(r"https?://", ident):
                want_url.append(ident)

        found: dict[str, dict[str, Any]] = {}
        if want_pmid:
            try:
                r = _get(PUBMED, params={"db": "pubmed", "id": ",".join(want_pmid), "retmode": "json"})
                found.update(parse_pubmed(r.json(), want_pmid))
            except (requests.RequestException, ValueError):
                pass
        for doi in want_doi:
            try:
                r = _get(CROSSREF + doi)
                rec = parse_crossref(r.json()) if r.ok else None
                if rec:
                    found[key_of("doi", doi)] = rec
            except (requests.RequestException, ValueError):
                pass
        for url in want_url:
            host = urlparse(url).hostname or ""
            rec: dict[str, Any] = {"kind": "web", "site": host.removeprefix("www."), "title": "", "ok": False}
            if is_public_host(host):
                try:
                    r = _get(url, stream=True, allow_redirects=True)
                    rec["ok"] = r.status_code < 400
                    if "html" in r.headers.get("content-type", "") and r.ok:
                        chunk = next(r.iter_content(150_000), b"")
                        rec["title"] = parse_title(decode_page(chunk, r.headers.get("content-type", "")))
                    r.close()
                except (requests.RequestException, ValueError):
                    pass
            found[key_of("url", url)] = rec

        with self._lock:
            if found:
                self._cache.update(found)
                self._save()
        out.update(found)
        return out
