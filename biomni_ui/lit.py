"""Literature helpers the agent can import from its code: `from biomni_ui.lit import author_papers, pubmed_search`.

They exist because the stock tools are unreliable here: `query_scholar` needs Google Scholar (unreachable) and
`query_pubmed` does a free-text search, which cannot tell the authors apart. These talk to PubMed E-utilities and
OpenAlex directly and print results in a fixed layout (PMID / title / authors / journal / year / affiliation), so
the workbench can number and check every citation.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OPENALEX = "https://api.openalex.org/"
CROSSREF = "https://api.crossref.org/works"  # no key; no contact address is sent with it
UA = {"User-Agent": "biomni-lite/0.1 (local research use)"}
TIMEOUT = 20
MAX_GROUPS = 6
MAX_PER_GROUP = 8


_CACHE: dict[str, tuple[float, requests.Response]] = {}
CACHE_SECONDS = 15 * 60


def _get(url: str, **kw: Any) -> requests.Response:
    """GET with a short in-memory cache (the same search twice in a session costs nothing) and one retry on 429/5xx."""
    headers = kw.pop("headers", {})
    key = url + "?" + repr(sorted((kw.get("params") or {}).items()))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        try:
            hit[1].from_cache = True
        except AttributeError:  # some response classes (requests_cache's CachedResponse) do not allow new attributes; that must not fail the request
            pass
        return hit[1]
    r = None
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={**UA, **headers}, **kw)
        except requests.RequestException:
            with requests.Session() as s:  # some academic hosts fail through the system proxy
                s.trust_env = False
                r = s.get(url, timeout=TIMEOUT, headers={**UA, **headers}, **kw)
        if r.status_code in (429, 500, 502, 503) and attempt == 0:
            time.sleep(1.5)
            continue
        break
    r.raise_for_status()
    if len(_CACHE) > 200:
        _CACHE.clear()
    _CACHE[key] = (time.time(), r)
    return r


_CJK = re.compile(r"[\u4e00-\u9fff]")
_COMPOUND = ("欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙", "慕容", "令狐", "司徒", "夏侯", "端木", "轩辕")


def _cjk_parts(name: str) -> tuple[str, list[str]] | None:
    """(family pinyin, given-name syllables) of a Chinese name, or None if it is not one."""
    text = name.strip()
    if not _CJK.search(text):
        return None
    try:
        from pypinyin import lazy_pinyin, load_single_dict
    except ImportError:
        return None
    load_single_dict({ord("伽"): "jia"})  # the default reading (qie / ga) is wrong for given names
    chars = re.sub(r"[\s·.]+", "", text)
    n = 2 if chars[:2] in _COMPOUND else 1
    if len(chars) <= n:
        return None
    return "".join(lazy_pinyin(chars[:n])).capitalize(), lazy_pinyin(chars[n:])


def to_latin(name: str) -> str:
    """"王小明" -> "Wang Xiaoming" (surname first, as Chinese names are written); other names are returned unchanged.

    PubMed and OpenAlex index authors in Latin script, so a Chinese name searched as-is finds nothing.
    """
    parts = _cjk_parts(name)
    return f"{parts[0]} {''.join(parts[1]).capitalize()}" if parts else name


def name_variants(name: str) -> list[tuple[str, str, str]]:
    """Possible (last name, first initials, full given name) readings of a person's name.

    "Li Xiaohua" and "Xiaohua Li" are both accepted; for Chinese names the order is ambiguous, so both are tried.
    """
    cjk = _cjk_parts(name)
    if cjk:
        family, syl = cjk
        return [(family, "".join(x[0] for x in syl).upper(), "".join(syl).capitalize())]
    parts = [p for p in re.split(r"[\s,]+", name.strip()) if p]
    if len(parts) < 2:
        return [(parts[0], "", "")] if parts else []
    out = []
    for last, given in ((parts[0], parts[1:]), (parts[-1], parts[:-1])):
        g = "".join(given)
        out.append((last, "".join(x[0] for x in given).upper(), g))
    # "Li XH" style: the second token is already initials
    if len(parts) == 2 and parts[1].isupper() and len(parts[1]) <= 3:
        out = [(parts[0], parts[1], "")]
    seen, uniq = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def build_terms(name: str, orcid: str | None = None, affiliation: str | None = None) -> list[str]:
    terms = []
    if orcid:
        terms.append(f"{orcid}[Auid]")
    strict = bool(_CJK.search(name))
    for last, ini, given in name_variants(name):
        for first in dict.fromkeys(x for x in ((ini, given) if strict else (ini, ini[:1], given)) if x):
            terms.append(f"{last} {first}[Author]")
    if affiliation and strict:
        # Older papers print only "Wang X". An affiliation filter makes that safe enough, so search for it too.
        for last, ini, _ in name_variants(name):
            if ini:
                terms.append(f"{last} {ini[0]}[Author]")
    terms = list(dict.fromkeys(terms))
    if affiliation:
        affs = [a.strip() for a in re.split(r"[|;；]", affiliation) if a.strip()]
        clause = " OR ".join(f'"{a}"[Affiliation]' for a in affs)
        terms = [f"({t}) AND ({clause})" for t in terms]
    return terms


def parse_records(xml_text: str) -> list[dict[str, Any]]:
    """PubMed efetch XML -> records with every author and that author's affiliation."""
    out = []
    root = ET.fromstring(xml_text)
    for art in root.iter("PubmedArticle"):
        pmid = (art.findtext(".//MedlineCitation/PMID") or "").strip()
        title = "".join(art.find(".//ArticleTitle").itertext()).strip().rstrip(".") if art.find(".//ArticleTitle") is not None else ""
        year = art.findtext(".//JournalIssue/PubDate/Year") or (art.findtext(".//JournalIssue/PubDate/MedlineDate") or "")[:4]
        authors = []
        for a in art.iter("Author"):
            last, ini = a.findtext("LastName") or "", a.findtext("Initials") or ""
            fore = a.findtext("ForeName") or ""
            if last:
                aff = " ".join((a.findtext("AffiliationInfo/Affiliation") or "").split())
                authors.append({"last": last, "initials": ini, "fore": fore, "affiliation": aff})
        doi = next((e.text for e in art.iter("ArticleId") if e.get("IdType") == "doi"), "")
        out.append({"pmid": pmid, "title": title, "year": year, "journal": art.findtext(".//Journal/Title") or "",
                    "doi": doi or "", "authors": authors})
    return out


def matches_author(rec: dict[str, Any], name: str, initials_ok: bool = True, first_initial_ok: bool = False) -> dict[str, Any] | None:
    """The author entry of `rec` that is `name` (any accepted reading), or None. Kills same-name pollution."""
    strict = bool(_CJK.search(name))
    for last, ini, given in name_variants(name):
        for a in rec["authors"]:
            if a["last"].lower() != last.lower():
                continue
            if strict:
                fore = re.sub(r"[^a-z]", "", a["fore"].lower())
                if fore.startswith(given.lower()) or (initials_ok and len(fore) <= 2 and a["initials"].upper() == ini):
                    return a
                if first_initial_ok and ini and a["initials"][:1].upper() == ini[0]:  # "Wang X": only with an affiliation filter
                    return a
                continue
            if not ini or a["initials"].upper().startswith(ini[:1]) or (given and a["fore"].lower().startswith(given.lower()[:3])):
                return a
    return None


def pubmed_ids(term: str, retmax: int = 50, attempts: int = 4) -> list[str]:
    """The PMIDs for a PubMed query. NCBI sometimes answers with a server error (HTTP 500, "Search Backend failed") or with an error
    body instead of a result list (rate limit, a bad query). Both are retried with a growing pause, which outlasts most outages;
    then the failure is reported with NCBI's own words instead of a KeyError."""
    last = "no result list"
    for n in range(attempts):
        try:
            r = _get(EUTILS + "esearch.fcgi", params={"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", "sort": "date"})
        except requests.RequestException as e:
            last = f"HTTP error {type(e).__name__}: {str(e)[:120]}"
        else:
            data = r.json() if r.content else {}
            result = (data or {}).get("esearchresult") or {}
            if "idlist" in result:
                return result["idlist"]
            last = str(result.get("ERROR") or result.get("errorlist") or (data or {}))[:200]
        if n + 1 < attempts:
            time.sleep((2, 5, 10, 15)[min(n, 3)])
    raise RuntimeError(f"PubMed search returned no results ({last}). NCBI's search service may be temporarily unavailable; try again later, or use another query.")


def fetch_records(pmids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(0, len(pmids), 100):
        r = _get(EUTILS + "efetch.fcgi", params={"db": "pubmed", "id": ",".join(pmids[i:i + 100]), "retmode": "xml"})
        out.extend(parse_records(r.text))
        if not getattr(r, "from_cache", False):
            time.sleep(0.34)  # NCBI allows about 3 requests per second without a key
    return out


def _fmt(rec: dict[str, Any], who: dict[str, Any] | None = None) -> str:
    authors = ", ".join(f"{a['last']} {a['initials']}" for a in rec["authors"][:6]) + (" et al." if len(rec["authors"]) > 6 else "")
    line = f"PMID: {rec['pmid']} | {rec['title']} | {authors} | {rec['journal']} {rec['year']}"
    if rec.get("doi"):
        line += f" | DOI: {rec['doi']}"
    if who and who.get("affiliation"):
        line += f"\n    Affiliation: {who['affiliation'][:160]}"
    return line


def save_csv(rows: list[tuple[dict[str, Any], dict[str, Any] | None]], stem: str) -> str:
    """Write the full list (all authors, DOI, the matched author's affiliation) next to the work; returns the file name."""
    import csv
    from pathlib import Path

    name = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")[:40] or "papers"
    path = Path(f"papers_{name}.csv")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["PMID", "Year", "Title", "Journal", "DOI", "All authors", "Affiliation of the matched author"])
        for r, who in rows:
            w.writerow([r["pmid"], r["year"], r["title"], r["journal"], r["doi"],
                        "; ".join(f"{a['last']} {a['fore'] or a['initials']}".strip() for a in r["authors"]),
                        (who or {}).get("affiliation", "")])
    return path.name


def pubmed_search(query: str, max_results: int = 10) -> str:
    """Free-text PubMed search, printed with PMID, title, authors, journal and year.

    When PubMed errors or finds nothing, Europe PMC and then Crossref are tried; the answer says which source gave it.
    """
    try:
        recs = fetch_records(pubmed_ids(query, max_results))
        failure = "PubMed found no results"
    except Exception as e:  # NCBI answers some queries with a server error; the other sources can still answer
        recs, failure = [], f"PubMed error: {type(e).__name__}"
    if recs:
        return f"Query: {query}\n{len(recs)} papers:\n" + "\n".join(_fmt(r) for r in recs)
    return _fallback_search(query, max_results, failure)


def _fallback_search(query: str, max_results: int, failure: str) -> str:
    """Europe PMC, then Crossref, for a question PubMed could not answer."""
    notes = [failure]
    try:
        # PubMed field tags such as [Title/Abstract] make Europe PMC find nothing, so they are removed; SRC:MED keeps the records PubMed
        # itself indexes; relevance order, because newest-first returns unrelated recent papers
        plain = re.sub(r"\[(?:Title/Abstract|Title|tiab|Author|dp|pdat|MeSH Terms|MeSH)\]", "", query, flags=re.I)
        text = europepmc_search(f"({plain}) AND (SRC:MED)", max_results, by_relevance=True)
    except Exception as e:
        text = ""
        notes.append(f"Europe PMC error: {type(e).__name__}")
    if text and "found no results" not in text:
        return f"{text}\n({'; '.join(notes)}; using the PubMed-indexed records in Europe PMC)"
    notes.append("Europe PMC found no results")
    try:
        text = crossref_search(query, max_results)
    except Exception as e:
        text = ""
        notes.append(f"Crossref error: {type(e).__name__}")
    if text:
        return f"{text}\n({'; '.join(notes)}; using Crossref)"
    return f"Found no results ({'; '.join(notes)}). Query: {query}"


def crossref_search(query: str, max_results: int = 10) -> str:
    """Crossref bibliographic search: papers and DOIs without a key. Used only when PubMed and Europe PMC cannot answer."""
    r = _get(CROSSREF, params={"query.bibliographic": query, "rows": max_results,
                               "select": "DOI,title,author,container-title,issued,type"})
    items = (r.json().get("message") or {}).get("items") or []
    rows = []
    for it in items[:max_results]:
        title = " ".join(((it.get("title") or [""])[0] or "").split())[:160]
        year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        journal = (it.get("container-title") or [""])[0] or ""
        if len(title) < 15 or title.lower() in ("abstract title", "abstract") or (not year and not journal):
            continue  # placeholder records (a supplement, an abstract stub) are not citations
        journal = journal or "journal unknown"
        names = [f"{a.get('family') or ''} {(a.get('given') or '')[:1]}".strip() for a in (it.get("author") or [])]
        who = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "") or "author unknown"
        rows.append(f"{year or 'year unknown'} | {journal} | {title} | {who} | DOI {it.get('DOI', '')}")
    if not rows:
        return ""
    return f"Query: {query}\n{len(rows)} papers (Crossref):\n" + "\n".join(rows)


def author_papers(name: str, affiliation: str | None = None, orcid: str | None = None, max_results: int = 30,
                  max_groups: int = MAX_GROUPS, per_group: int = MAX_PER_GROUP, compact: bool = False) -> str:
    """Papers by one author, with namesakes separated.

    Tries every plausible spelling of the name, keeps only papers where that author really appears, and groups the
    hits by the affiliation printed on the paper so different people with the same name can be told apart. Pass
    `affiliation` (e.g. "Tsinghua") or `orcid` to narrow it down.
    """
    terms = build_terms(name, orcid, affiliation)
    ids: list[str] = []
    for t in terms:
        try:
            ids += pubmed_ids(t, max_results)
        except requests.RequestException:
            continue
        time.sleep(0.34)  # NCBI allows about 3 requests per second without a key
    ids = list(dict.fromkeys(ids))
    if not ids:
        return f"PubMed has no papers by {name}. Queries tried: {terms}"
    recs = fetch_records(ids[: max_results * 3])
    hits = [(r, matches_author(r, name, initials_ok=False, first_initial_ok=bool(affiliation))) for r in recs]
    hits = [(r, a) for r, a in hits if a]
    note = ""
    if not hits and _CJK.search(name):
        # No record spells out the given name: fall back to initials only, which cannot tell people apart.
        hits = [(r, matches_author(r, name)) for r in recs]
        hits = [(r, a) for r, a in hits if a]
        note = "(no paper gives the full name; matched on initials only, so the risk of same-name people is high)"
    if not hits:
        return f"Found {len(recs)} candidate papers, but none lists {name} as an author (same-name matches removed). Tried: {terms}"

    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for r, a in hits:
        key = (a["affiliation"].split(",")[0].strip() or "(the paper gives no affiliation)")[:60]
        groups.setdefault(key, []).append((r, a))
    lines = [f"Author {name} (pinyin {to_latin(name)}): after checking the author lists, {len(hits)} papers kept ({len(recs)} candidates).{note}".replace("(pinyin " + name + ")", ""), f"Query: {terms}"]
    if len(groups) > 1:
        lines.append(f"Note: these papers come from {len(groups)} different affiliations and may belong to different people with the same name; tell them apart by affiliation or ORCID.")
    lines.append(f"Full list ({len(hits)} papers, with all authors and affiliations) saved: {save_csv(hits, 'author_' + to_latin(name))}")
    if compact:
        people = cluster_identities(hits)
        lines.append(f"These papers are grouped by “shared co-authors / same institution” into {len(people)} possibly different people (same-name people are kept apart; one person who changed affiliation stays together if the co-authors are the same):")
        multi = [g for g in people if len(g) >= 2]
        single = [g[0] for g in people if len(g) == 1]
        for k, g in enumerate(multi[:max_groups], 1):
            lines.append(f"\n## Possible person {k} ({describe_cluster(g)})")
            lines += [_compact(r) for r, a in g[:per_group]]
            if len(g) > per_group:
                lines.append(f"    …{len(g) - per_group} more papers not listed")
        if single:
            lines.append(f"\n## Single records that do not cluster with other papers ({len(single)}; most are probably different people; use one only when the affiliation or topic matches exactly)")
            lines += [f"{_compact(r)} | Affiliation: {' '.join(a['affiliation'].split(',')[:2])[:80]}" for r, a in single[:25]]
        return "\n".join(lines)
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    for key, items in ranked[:max_groups]:
        lines.append(f"\n## Affiliation: {key} ({len(items)} papers)")
        if compact:  # one short line per paper, so a long list still fits in the model's context
            lines += [_compact(r) for r, a in items[:per_group]]
        else:
            lines += [_fmt(r, a) for r, a in items[:per_group]]
        if len(items) > per_group:
            lines.append(f"    …{len(items) - per_group} more papers from this affiliation not listed (newest first)")
    if len(ranked) > max_groups:
        rest = sum(len(i) for _, i in ranked[max_groups:])
        lines.append(f"\n({len(ranked) - max_groups} more affiliations with {rest} papers not listed; add the affiliation parameter to narrow the search)")
    return "\n".join(lines)


def _compact(r: dict[str, Any]) -> str:
    """year | journal | title | first three authors ... last author | PMID | DOI: enough to judge who the co-authors are."""
    names = [f"{a['last']} {a['initials']}".strip() for a in r["authors"]]
    who = ", ".join(names[:3]) + (f" … {names[-1]}" if len(names) > 4 else (", " + ", ".join(names[3:]) if len(names) > 3 else ""))
    return f"{r['year']} | {r['journal']} | {r['title'][:140]} | {who} | PMID {r['pmid']}" + (f" | DOI {r['doi']}" if r["doi"] else "")


def openalex_author_candidates(name: str, limit: int = 5) -> str:
    """Candidate author profiles (institution, paper count, ORCID) to decide which person is meant."""
    latin = to_latin(name)
    queries = list(dict.fromkeys([latin, name]))
    rows, seen = [], set()
    for q in queries:
        r = _get(OPENALEX + "authors", params={"search": q, "per-page": limit})
        for a in r.json().get("results", []):
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            inst = (a.get("last_known_institutions") or [{}])[0].get("display_name", "")
            topics = ", ".join(t["display_name"] for t in (a.get("topics") or [])[:3])
            rows.append(f"- {a['display_name']} | Affiliation: {inst or 'unknown'} | Papers: {a.get('works_count')} | ORCID: {a.get('orcid') or 'none'} | Topics: {topics}\n  {a['id']}")
    shown = f"{name} (pinyin search: {latin})" if latin != name else name
    return f"OpenAlex author candidates named {shown}:\n" + ("\n".join(rows[: limit * 2]) if rows else "none found")



def paper_abstracts(pmids: list[str] | str) -> str:
    """Abstract, authors, journal, year and DOI for PubMed IDs (a list, or a comma-separated string)."""
    ids = [x.strip() for x in (pmids.split(",") if isinstance(pmids, str) else pmids) if str(x).strip()]
    if not ids:
        return "No PMID given."
    out = []
    for batch_start in range(0, len(ids), 100):
        r = _get(EUTILS + "efetch.fcgi", params={"db": "pubmed", "id": ",".join(ids[batch_start:batch_start + 100]), "retmode": "xml"})
        root = ET.fromstring(r.text)
        for art in root.iter("PubmedArticle"):
            rec = parse_records(ET.tostring(art, encoding="unicode"))[0]
            abstract = " ".join("".join(n.itertext()).strip() for n in art.iter("AbstractText")) or "(no abstract for this entry)"
            out.append(_fmt(rec) + "\n    Abstract: " + abstract[:1800])
    return "\n\n".join(out) or "PubMed returned no records for these PMIDs."


def europepmc_search(query: str, max_results: int = 10, since: str | None = None, by_relevance: bool = False) -> str:
    """Search Europe PMC (PubMed plus preprints from bioRxiv/medRxiv/Research Square and more).

    `since` is an ISO date such as "2026-10-01"; only papers first published on or after it are returned.
    """
    q = query if not since else f"({query}) AND (FIRST_PDATE:[{since} TO 3000-01-01])"
    r = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
             params={"query": q, "format": "json", "pageSize": max_results, "resultType": "core",
                     **({} if by_relevance else {"sort": "P_PDATE_D desc"})})  # by_relevance: Europe PMC ranks by how well a record matches
    data = r.json()
    rows = data.get("resultList", {}).get("result", [])
    if not rows:
        return f"Europe PMC found no results. Query: {q}"
    order = "most relevant" if by_relevance else "newest"
    lines = [f"Query: {q}\nEurope PMC: {data.get('hitCount')} papers in all; listing the {order} {len(rows)}:"]
    for x in rows:
        ident = f"PMID: {x['pmid']}" if x.get("pmid") else f"{x.get('source')}: {x.get('id')}"
        authors = (x.get("authorString") or "").rstrip(".")
        if authors.count(",") > 5:
            authors = ", ".join(authors.split(", ")[:6]) + " et al."
        line = f"{ident} | {(x.get('title') or '').rstrip('.')} | {authors} | {x.get('journalTitle') or (x.get('bookOrReportDetails') or {}).get('publisher') or ('preprint' if x.get('source') == 'PPR' else '')} {x.get('pubYear', '')}"
        if x.get("doi"):
            line += f" | DOI: {x['doi']}"
        if x.get("source") == "PPR":
            line += " | [preprint, not peer reviewed]"
        lines.append(line)
    return "\n".join(lines)


# ---- telling namesakes apart: group papers into probable people ---------------------------------------------------

def _head(aff: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (aff.split(",")[0] if aff else "").lower()).strip()


def _coauthor_keys(rec: dict[str, Any], me: dict[str, Any]) -> tuple[set[str], set[str]]:
    """(strong, weak) co-author keys of one paper: strong = surname + spelled-out given name, weak = surname + initial."""
    strong, weak = set(), set()
    for x in rec["authors"]:
        if x is me or (x["last"], x["initials"]) == (me["last"], me["initials"]):
            continue
        fore = re.sub(r"[^a-z]", "", x["fore"].lower())
        if len(fore) >= 3:
            strong.add(f"{x['last'].lower()} {fore}")
        weak.add(f"{x['last'].lower()} {x['initials'][:1].lower()}")
    return strong, weak


def cluster_identities(hits: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[list[tuple[dict[str, Any], dict[str, Any]]]]:
    """Group a name's papers into probable people.

    Two papers belong to one person when they share a co-author whose full name is spelled out, or two initial-only
    co-authors, or the same institution printed on both. This is the signal a human uses ("same lab, same people").
    """
    n = len(hits)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    keys = [_coauthor_keys(r, a) for r, a in hits]
    heads = [_head(a["affiliation"]) for _, a in hits]
    for i in range(n):
        for j in range(i + 1, n):
            same_lab = bool(keys[i][0] & keys[j][0]) or len(keys[i][1] & keys[j][1]) >= 3
            same_inst = len(heads[i]) > 12 and heads[i] == heads[j]
            if same_lab or same_inst:
                parent[find(i)] = find(j)
    groups: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for i, h in enumerate(hits):
        groups.setdefault(find(i), []).append(h)
    return sorted(groups.values(), key=lambda g: (-len(g), -max(int(r["year"] or 0) if str(r["year"]).isdigit() else 0 for r, _ in g)))


def describe_cluster(group: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    from collections import Counter

    years = sorted(int(r["year"]) for r, _ in group if str(r["year"]).isdigit())
    affs = Counter(" ".join(a["affiliation"].split(",")[:2]).strip()[:90] for _, a in group if a["affiliation"])
    co = Counter(k for r, a in group for k in _coauthor_keys(r, a)[0])
    journals = Counter(r["journal"] for r, _ in group if r["journal"])
    bits = [f"{len(group)} papers" + (f", {years[0]}–{years[-1]}" if years else "")]
    if affs:
        bits.append("Affiliation: " + "; ".join(k for k, _ in affs.most_common(2)))
    if co:
        bits.append("Frequent co-authors: " + ", ".join(k.title() for k, _ in co.most_common(4)))
    if journals:
        bits.append("Journals: " + ", ".join(k for k, _ in journals.most_common(3)))
    return ", ".join(bits)


# ---- OpenAlex: covers preprints (Zenodo, arXiv, bioRxiv) that PubMed never indexes ---------------------------------

def openalex_author_works(author_id: str, limit: int = 40) -> str:
    """The works OpenAlex attributes to one author profile, newest first, each with the institution printed on THAT paper.

    OpenAlex builds profiles by an algorithm and often merges namesakes (measured: a Shanghai cell-therapy researcher's
    profile also held two University of Georgia toxicology papers). So the per-paper institution is shown, and a
    profile whose papers carry different institutions is flagged instead of being presented as one person.
    """
    r = _get(OPENALEX + "works", params={"filter": f"author.id:{author_id}", "per-page": limit, "sort": "publication_date:desc",
                                         "select": "title,publication_year,primary_location,doi,cited_by_count,type,authorships"})
    rows, insts = [], {}
    for w in r.json().get("results", []):
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or w.get("type") or ""
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        mine = [au for au in (w.get("authorships") or []) if ((au.get("author") or {}).get("id") or "").endswith(author_id)]
        inst = [i["display_name"] for au in mine for i in (au.get("institutions") or [])]
        if inst:
            insts[inst[0]] = insts.get(inst[0], 0) + 1
        rows.append(f"{w.get('publication_year')} | {venue[:40]} | {(w.get('title') or '')[:130]} | " + (f"DOI {doi} | " if doi else "") + f"cited {w.get('cited_by_count')} times"
                    + (f" | Affiliation on this paper: {', '.join(inst[:2])}" if inst else ""))
    warn = ""
    if len(insts) >= 2:
        warn = ("⚠ The affiliations on the papers in this profile are inconsistent (" + "; ".join(f"{k} {v} papers" for k, v in insts.items())
                + "). This person may have changed affiliation, or OpenAlex may have merged different people with the same name; check whether the topics and co-authors are continuous. Do not conclude from the profile's “latest affiliation” alone.\n")
    return warn + "\n".join(rows)


def openalex_profile(name: str, top: int = 2) -> str:
    """OpenAlex author candidates for a name, plus the works of the biggest ones (profiles can mix namesakes: say so)."""
    latin = to_latin(name)
    seen, cands = set(), []
    for q in dict.fromkeys([latin, name]):
        r = _get(OPENALEX + "authors", params={"search": q, "per-page": 8})
        for a in r.json().get("results", []):
            if a["id"] not in seen:
                seen.add(a["id"])
                cands.append(a)
    cands.sort(key=lambda a: -(a.get("works_count") or 0))
    out = [f"OpenAlex author profile candidates ({name}). Note: OpenAlex profiles are clustered by an algorithm, so people with the same name may be merged; cross-check affiliation, topic and year. Preprints (Zenodo, arXiv, bioRxiv) can only be found here."]
    for a in cands[:6]:
        inst = (a.get("last_known_institutions") or [{}])[0].get("display_name") or "unknown"
        topics = ", ".join(t["display_name"] for t in (a.get("topics") or [])[:3])
        out.append(f"- {a['id'].split('/')[-1]} | {a['display_name']} | latest affiliation in the profile (from the algorithm; it often merges same-name people, for reference only): {inst} | papers {a.get('works_count')}, cited {a.get('cited_by_count')} times | ORCID: {(a.get('orcid') or 'none').replace('https://orcid.org/', '')} | Topics: {topics}")
    for a in [c for c in cands if (c.get("works_count") or 0) >= 5][:top]:
        try:
            works = openalex_author_works(a["id"].split("/")[-1], 40)
        except requests.RequestException:
            continue
        if works:
            out.append(f"\n### OpenAlex profile {a['id'].split('/')[-1]} ({a['display_name']}, {a.get('works_count')} papers): works, newest first:\n{works}")
    return "\n".join(out)


# ---- identity anchors: ORCID, Zenodo, Semantic Scholar -------------------------------------------------------------

ORCID = "https://pub.orcid.org/v3.0/"
ZENODO = "https://zenodo.org/api/records"
S2 = "https://api.semanticscholar.org/graph/v1/author/search"


def _json(url: str, **kw: Any) -> Any:
    return _get(url, headers={"Accept": "application/json"}, **kw).json()


def orcid_candidates(name: str, rows: int = 8) -> list[str]:
    """People with this name in ORCID (self-registered, so a reliable 'who exists' list): iD, name, institution."""
    out = []
    for last, _ini, given in name_variants(name)[:2]:
        if not given:
            continue
        data = _json(ORCID + "expanded-search/", params={"q": f"family-name:{last} AND given-names:{given}", "rows": rows})
        for x in data.get("expanded-result") or []:
            line = f"ORCID {x['orcid-id']} | {x.get('given-names', '')} {x.get('family-names', '')} | Affiliation: {'; '.join(x.get('institution-name') or []) or 'not registered'}"
            if line not in out:
                out.append(line)
    return out


def zenodo_records(name: str, size: int = 25) -> list[str]:
    """Zenodo deposits (preprints, datasets, reports) whose creator is this name: date | title | DOI."""
    out, seen = [], set()
    for last, _ini, given in name_variants(name)[:2]:
        if not given:
            continue
        data = _json(ZENODO, params={"q": f'creators.name:"{last}, {given}"', "size": size, "sort": "mostrecent"})
        for h in (data.get("hits") or {}).get("hits", []):
            m = h.get("metadata", {})
            conc = h.get("conceptdoi") or h.get("doi")
            if conc in seen:
                continue
            seen.add(conc)
            creators = "; ".join(f"{c.get('name')} ({c.get('affiliation') or 'no affiliation'})" for c in (m.get("creators") or [])[:3])
            out.append(f"{(m.get('publication_date') or '')[:10]} | {(m.get('title') or '')[:120]} | DOI {conc} | Authors: {creators}")
    return out


def s2_candidates(name: str) -> list[str]:
    data = _json(S2, params={"query": to_latin(name) if _CJK.search(name) else name, "fields": "name,affiliations,paperCount,hIndex,citationCount", "limit": 5})
    return [f"SemanticScholar {a['authorId']} | {a['name']} | papers {a.get('paperCount')}, h-index {a.get('hIndex')}, cited {a.get('citationCount')} times | Affiliation: {'; '.join(a.get('affiliations') or []) or 'not registered'}" for a in data.get("data", [])]


def identity_sources(name: str) -> str:
    """Independent records of who carries this name and what they deposited. Each source may fail alone."""
    parts = []
    for title, fn in (("Same-name entries in ORCID", orcid_candidates), ("Semantic Scholar author profiles", s2_candidates), ("Zenodo archive (includes preprints and reports; not in PubMed)", zenodo_records)):
        try:
            rows = fn(name)
        except Exception as e:
            rows = [f"({title}: not available for now: {type(e).__name__})"]
        if rows:
            parts.append(f"### {title}\n" + "\n".join(rows))
    return "\n\n".join(parts)


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"<[^>]+>", "", t or "").lower()).strip()


def crossref_lookup(title: str) -> dict[str, str]:
    """DOI, journal and year of a work found by its exact title (accepted only when the titles match), {} otherwise."""
    try:
        r = _get("https://api.crossref.org/works", params={"query.bibliographic": title, "rows": 2, "select": "DOI,title,container-title,issued"})
        for item in r.json().get("message", {}).get("items", []):
            if _norm_title((item.get("title") or [""])[0]) == _norm_title(title):
                year = ((item.get("issued") or {}).get("date-parts") or [[""]])[0][0]
                return {"doi": item.get("DOI", ""), "journal": (item.get("container-title") or [""])[0], "year": str(year or "")}
    except Exception:
        pass
    return {}


def pubmed_title_lookup(title: str) -> str:
    """PMID of the one PubMed record whose title is exactly `title` ("" when none or ambiguous)."""
    try:
        ids = pubmed_ids(f'"{re.sub(chr(34), "", title).strip().rstrip(".")}"[Title]', 2)
        return ids[0] if len(ids) == 1 else ""
    except Exception:
        return ""


def orcid_works(orcid: str, limit: int = 40) -> list[str]:
    """The works a person lists on their own ORCID record (self-curated, so the strongest identity anchor).

    Layout: year | title | journal | DOI | PMID. ORCID entries often carry no identifiers at all, so a missing DOI is looked
    up by exact title in Crossref (same title only); what cannot be found is left out of the line instead of invented.
    """
    from concurrent.futures import ThreadPoolExecutor

    data = _json(f"{ORCID}{orcid}/works")
    items = []
    for g in data.get("group", []):
        w = (g.get("work-summary") or [{}])[0]
        ids = [(e.get("external-id-type"), e.get("external-id-value")) for e in ((w.get("external-ids") or {}).get("external-id") or [])]
        items.append({
            "year": str((((w.get("publication-date") or {}).get("year")) or {}).get("value", "")),
            "title": (((w.get("title") or {}).get("title")) or {}).get("value", ""),
            "journal": ((w.get("journal-title") or {}).get("value")) or "",
            "doi": next((v for t, v in ids if t == "doi"), ""),
            "pmid": next((v for t, v in ids if t == "pmid"), ""),
        })
    items.sort(key=lambda x: x["year"], reverse=True)
    items = items[:limit]
    missing = [it for it in items if not it["doi"] and not it["pmid"] and it["title"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for it, hit in zip(missing, pool.map(lambda x: crossref_lookup(x["title"]), missing)):
            it["doi"] = hit.get("doi", "")
            it["journal"] = it["journal"] or hit.get("journal", "")
            it["year"] = it["year"] or hit.get("year", "")
    for it in missing:  # Crossref missed it: an exact title in PubMed gives the PMID (a few at a time, NCBI allows ~3/s)
        if not it["doi"]:
            it["pmid"] = pubmed_title_lookup(it["title"])
            time.sleep(0.34)
    return [f"{it['year']} | {it['title'][:130]}" + (f" | {it['journal']}" if it["journal"] else "") + (f" | DOI {it['doi']}" if it["doi"] else "") + (f" | PMID {it['pmid']}" if it["pmid"] else "") for it in items]


def identity_sources(name: str) -> str:  # noqa: F811  (extends the earlier version with the ORCID records themselves)
    """Independent records of who carries this name and what they deposited. Each source may fail alone."""
    parts = []
    orcids: list[str] = []
    try:
        cands = orcid_candidates(name)
        orcids = [c.split(" | ")[0].replace("ORCID ", "") for c in cands]
        parts.append("### Same-name entries in ORCID (affiliations from the person's own registered employment history)\n" + "\n".join(cands)) if cands else None
    except Exception as e:
        parts.append(f"### Same-name entries in ORCID\n(not available for now: {type(e).__name__})")
    from concurrent.futures import ThreadPoolExecutor

    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            return [f"(not available for now: {type(e).__name__})"]

    with ThreadPoolExecutor(max_workers=6) as pool:  # independent look-ups run at once
        works_jobs = [(oid, pool.submit(safe, orcid_works, oid)) for oid in orcids[:3]]
        s2_job, zen_job = pool.submit(safe, s2_candidates, name), pool.submit(safe, zenodo_records, name)
        for oid, job in works_jobs:
            works = job.result()
            if works:
                parts.append(f"### ORCID {oid}: works listed by the person ({len(works)} items)\n" + "\n".join(works))
        for title, job in (("Semantic Scholar author profiles", s2_job), ("Zenodo archive (includes preprints and reports; not in PubMed)", zen_job)):
            rows = job.result()
            if rows:
                parts.append(f"### {title}\n" + "\n".join(rows))
    return "\n\n".join(parts)


from biomni_ui import connectors as _connectors  # noqa: E402
_connectors.guard(globals())  # the switch of each database connector is checked on every call
