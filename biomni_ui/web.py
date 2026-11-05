"""Web search and page reading for the agent, without an API key.

The stock `search_google` scrapes Google (slow, often blocked here) and `advanced_web_search_claude` needs a Claude
model. These two use Bing's public result page, which is reachable from this network, and plain page fetching.
Results are printed in a fixed layout (number, title, site, link, snippet) so the answer can cite them.
"""

from __future__ import annotations

import base64
import re
import time
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
TIMEOUT = 20
_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_SECONDS = 15 * 60


def _fetch(url: str) -> requests.Response:
    hit = _CACHE.get(url)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
    except requests.RequestException:
        with requests.Session() as s:
            s.trust_env = False  # some hosts fail through the system proxy
            r = s.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    if len(_CACHE) > 100:
        _CACHE.clear()
    _CACHE[url] = (time.time(), r)
    return r


def real_url(href: str) -> str:
    """Bing wraps results in /ck/a?...&u=a1<base64 of the real address>; unwrap it."""
    p = urlparse(href)
    if p.netloc.endswith("bing.com") and p.path.startswith("/ck/"):
        u = (parse_qs(p.query).get("u") or [""])[0]
        if u.startswith("a1"):
            try:
                raw = u[2:] + "=" * (-len(u[2:]) % 4)
                return base64.urlsafe_b64decode(raw).decode("utf-8", "replace")
            except Exception:
                return href
    return href


def parse_results(html: str, limit: int) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    out = []
    for li in BeautifulSoup(html, "html.parser").select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        url = real_url(a["href"])
        if not url.startswith("http"):
            continue
        snippet = li.select_one(".b_caption p, .b_lineclamp2, .b_lineclamp3, .b_lineclamp4, p")
        out.append({"title": " ".join(a.get_text(" ").split()), "url": url,
                    "site": urlparse(url).netloc.removeprefix("www."),
                    "snippet": " ".join(snippet.get_text(" ").split()) if snippet else ""})
        if len(out) >= limit:
            break
    return out


def parse_so360(html: str, limit: int) -> list[dict[str, str]]:
    """360 search (so.com): handles rare Chinese company and person names that Bing's anonymous page mangles."""
    from bs4 import BeautifulSoup

    out = []
    for li in BeautifulSoup(html, "html.parser").select("li.res-list"):
        a = li.select_one("h3 a")
        if not a:
            continue
        url = a.get("data-mdurl") or a.get("href") or ""
        if not url.startswith("http"):
            continue
        desc = li.select_one(".res-desc, .res-rich, p")
        out.append({"title": " ".join(a.get_text(" ").split()), "url": url, "site": urlparse(url).netloc.removeprefix("www."),
                    "snippet": " ".join(desc.get_text(" ").split()) if desc else ""})
        if len(out) >= limit:
            break
    return out


def _bing(query: str, limit: int, language: str) -> list[dict[str, str]]:
    base = "https://cn.bing.com/search?q=" if language == "zh" else "https://www.bing.com/search?setlang=en&q="
    return parse_results(_fetch(base + quote_plus(query)).text, limit)


def _so360(query: str, limit: int, language: str) -> list[dict[str, str]]:
    return parse_so360(_fetch("https://www.so.com/s?q=" + quote_plus(query)).text, limit)


ENGINES = {"360": _so360, "bing": _bing}


def search_rows(query: str, max_results: int = 8, language: str = "zh", engine: str = "auto") -> tuple[list[dict[str, str]], list[str], list[str]]:
    """(results as {title, site, url, snippet}, engines that answered, errors). 360 first (good with Chinese names), Bing added when 360 gives fewer than 3."""
    order = ["360", "bing"] if engine == "auto" else [engine]
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    used: list[str] = []
    for name in order:
        fn = ENGINES.get(name)
        if not fn:
            raise ValueError(f"Unknown search engine {engine}; choose auto / 360 / bing.")
        try:
            found = fn(query, max_results, language)
        except requests.RequestException as e:
            errors.append(f"{name}: {type(e).__name__}")
            continue
        used.append(name)
        seen = {r["url"] for r in rows}
        rows += [r for r in found if r["url"] not in seen]
        if len(rows) >= 3:
            break
    return rows[:max_results], used, errors


def format_results(query: str, rows: list[dict[str, str]], used: list[str], errors: list[str], number=None) -> str:
    """The numbered text view of search results (title, site, link, snippet). With `number` (url, title -> int) every result carries the task-wide source number [@N]."""
    if not rows:
        return f"Web search returned no results (possibly rate-limited). Query: {query}" + (f"; errors: {', '.join(errors)}" if errors else "")
    lines = [f"Web search: {query} ({'+'.join(used)}, {len(rows)} results in all; summaries are not page text, so use read_webpage on a link for details)"]
    for i, r in enumerate(rows, 1):
        tag = f"[@{number(r['url'], r['title'])}]" if number else f"[{i}]"
        lines.append(f"{tag} {r['title']} | {r['site']}\n    {r['url']}\n    {r['snippet'][:240]}")
    return "\n".join(lines)


def web_search(query: str, max_results: int = 8, language: str = "zh", engine: str = "auto") -> str:
    """Search the web. Returns numbered results: title, site, link and snippet. Follow up with read_webpage.

    engine "auto" asks 360 first (good with Chinese company/person names) and adds Bing when 360 gives fewer than 3 hits;
    "360" or "bing" forces one of them.
    """
    try:
        rows, used, errors = search_rows(query, max_results, language, engine)
    except ValueError as e:
        return str(e)
    return format_results(query, rows, used, errors)


def read_webpage(url: str, max_chars: int = 6000) -> str:
    """Download a web page and return its title and main text (scripts/menus removed), truncated to max_chars."""
    from bs4 import BeautifulSoup

    if url.lower().split("?")[0].endswith(".pdf"):
        return read_pdf(url, "", max_chars)
    try:
        r = _fetch(url)
    except requests.RequestException as e:
        return f"Could not read the web page: {type(e).__name__}: {e}"
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype:
        return read_pdf(url, "", max_chars)
    if "html" not in ctype and "text" not in ctype:
        return f"This link is not a web page ({ctype}); use read_pdf or download the file instead."
    from .refs import decode_page

    soup = BeautifulSoup(decode_page(r.content, ctype), "html.parser")
    from urllib.parse import urljoin

    pdf_links = list(dict.fromkeys(urljoin(url, a["href"]) for a in soup.find_all("a", href=True) if a["href"].lower().split("?")[0].endswith(".pdf")))[:5]
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]):
        tag.decompose()
    title = " ".join((soup.title.get_text() if soup.title else "").split())
    node = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\n\s*\n+", "\n\n", "\n".join(ln.strip() for ln in node.get_text("\n").splitlines() if ln.strip()))
    more = len(text) - max_chars
    tail = (f"\n\n…({more} more characters not shown)" if more > 0 else "") + ("\n\nPDF links on the page (read them with read_pdf):\n" + "\n".join(pdf_links) if pdf_links else "")
    return f"Title: {title}\nLink: {url}\n\n{text[:max_chars]}" + tail


# ---- PDFs ---------------------------------------------------------------------------------------------------------

_PDF_CACHE: dict[str, bytes] = {}
MAX_PDF_BYTES = 60 * 1024 * 1024
PDF_SECONDS = 45


def _download_pdf(url: str) -> bytes:
    if url in _PDF_CACHE:
        return _PDF_CACHE[url]
    try:
        r = requests.get(url, headers=UA, timeout=60, stream=True)
    except requests.RequestException:
        with requests.Session() as s:
            s.trust_env = False
            r = s.get(url, headers=UA, timeout=60, stream=True)
    r.raise_for_status()
    data, size = [], 0
    for chunk in r.iter_content(1 << 20):
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ValueError(f"The PDF is larger than {MAX_PDF_BYTES // 1048576} MB; not downloaded")
        data.append(chunk)
    blob = b"".join(data)
    if not blob.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("The download is not a PDF (the site may have blocked it, or it may need a login)")
    if len(_PDF_CACHE) >= 3:
        _PDF_CACHE.pop(next(iter(_PDF_CACHE)))
    _PDF_CACHE[url] = blob
    return blob


def _terms(query: str) -> list[str]:
    stop = {"最近", "有什么", "有没有", "什么", "情况", "进展", "公司", "报告", "详细", "图文", "分析", "近两年", "关于", "请问", "帮我", "给我"}
    found = re.findall(r"[一-鿿A-Za-z0-9.%]{2,}", query or "")
    return [t for t in dict.fromkeys(found) if t not in stop]


def pdf_pages(blob: bytes, deadline: float) -> list[str]:
    """Text of every page that could be read before `deadline` (a 500-page filing must not hold the task up)."""
    import io

    import PyPDF2

    reader = PyPDF2.PdfReader(io.BytesIO(blob))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return []
    pages = []
    for page in reader.pages:
        if time.time() > deadline:
            break
        try:
            pages.append(" ".join((page.extract_text() or "").split()))
        except Exception:
            pages.append("")
    return pages


def select_pages(pages: list[str], query: str, max_chars: int) -> list[int]:
    """Page numbers (0-based, in reading order) that best match the query words; the first pages when there is no query."""
    terms = _terms(query)
    if not terms:
        picked, used = [], 0
        for i, t in enumerate(pages):
            if used >= max_chars:
                break
            picked.append(i)
            used += len(t)
        return picked
    scored = sorted(((sum(t.lower().count(w.lower()) * (2 if len(w) > 3 else 1) for w in terms), i) for i, t in enumerate(pages)), reverse=True)
    picked, used = [], 0
    for score, i in scored:
        if score <= 0 or used >= max_chars:
            break
        picked.append(i)
        used += min(len(pages[i]), max_chars // 3)
    return sorted(picked)


def read_pdf(url: str, query: str = "", max_chars: int = 8000) -> str:
    """Download a PDF (prospectus, annual report, paper) and return the pages that best match `query`, with page numbers.

    Long filings are searched page by page for the query words (company names, 'net loss', 现金, redemption liabilities ...), so the
    numbers you need come back with their page; without a query the first pages are returned.
    """
    try:
        blob = _download_pdf(url)
        pages = pdf_pages(blob, time.time() + PDF_SECONDS)
    except Exception as e:
        return f"Could not read the PDF: {type(e).__name__}: {e}"
    if not pages or not any(pages):
        return "This PDF has no extractable text (it may be a scan, which needs OCR)."
    chosen = select_pages(pages, query, max_chars)
    if not chosen:
        return f"The PDF has {len(pages)} pages, but no page contains the search term {query!r}. Try another search term, or read the first few pages without one."
    per = max(600, max_chars // max(1, len(chosen)))
    body = "\n\n".join(f"[page {i + 1}]\n{pages[i][:per]}" for i in chosen)
    return f"PDF: {url}\n{len(pages)} pages in all; the pages most relevant to \"{query or 'the start'}\": {', '.join(str(i + 1) for i in chosen)}:\n\n{body}"[: max_chars + 400]
