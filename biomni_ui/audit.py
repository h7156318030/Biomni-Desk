"""Citation audit: every source named in the final answer must have appeared in something the agent actually saw.

The prompt already tells the model to cite only what the tools returned, but a model sometimes adds a PMID/DOI/NCT/URL from
memory. That is cheap to detect without another model call: collect the identifiers in the answer, collect everything the
tools printed (plus the question and the scouting digest), and report the identifiers that appear nowhere in it.
"""

from __future__ import annotations

import re

_PMID = re.compile(r"\bPMID[:：]?\s*(\d{6,9})\b", re.I)
_STOP = r"\s)\]>）】》］（【《［，。；;,、：\"'”’*"  # ends of an identifier: ASCII and full-width brackets, punctuation, and the bold marker of Markdown
_DOI = re.compile(r"\b(10\.\d{4,9}/[^" + _STOP + r"]+)", re.I)
_NCT = re.compile(r"\b(NCT\d{8})\b", re.I)
_URL = re.compile(r"https?://[^" + _STOP + r"]+", re.I)


def _norm_url(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", u.strip().rstrip(".,/")).lower()


def cited(text: str) -> dict[str, set[str]]:
    """The identifiers an answer cites, by kind."""
    return {
        "PMID": set(_PMID.findall(text)),
        "DOI": {d.rstrip(".").lower() for d in _DOI.findall(text)},
        "NCT": {n.upper() for n in _NCT.findall(text)},
        "URL": {_norm_url(u) for u in _URL.findall(text)},
    }


# Links the provider's own search tool put in the answer carry this marker; they came out of a real search, not out of memory.
_SEARCH_LINK = re.compile(r"https?://[^" + _STOP + r"]*[?&]utm_source=openai[^" + _STOP + r"]*", re.I)


def unsupported(answer: str, seen: str) -> list[str]:
    """Identifiers cited in `answer` that never occur in `seen` (what the model was shown), as display strings."""
    have = cited(seen)
    seen_low = seen.lower()
    out: list[str] = []
    for kind, ids in cited(_SEARCH_LINK.sub(" ", answer)).items():
        for i in sorted(ids):
            if i in have[kind]:
                continue
            if kind == "URL":
                # a URL the tools printed without its tail, or the other way round, is still the same page
                if any(h and (h.startswith(i) or i.startswith(h)) for h in have["URL"]):
                    continue
                if i in seen_low:
                    continue
                # a page built from an identifier the tools returned (clinvar/variation/17677 from accession VCV000017677)
                tail = i.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
                if len(tail) >= 4 and re.search(r"\d", tail) and tail in seen_low:
                    continue
                # links to a DOI/PMID/NCT page are covered by the identifier itself
                if re.search(r"doi\.org/|pubmed\.ncbi\.nlm\.nih\.gov/\d+|clinicaltrials\.gov/study/NCT", i, re.I):
                    continue
            elif i.lower() in seen_low:
                continue
            out.append(f"{kind} {i}" if kind != "URL" else i)
    return out


def looks_like_calculation(question: str) -> bool:
    """A question made of numbers to combine (doses, dilutions): the answer needs no outside knowledge."""
    return len(re.findall(r"\d+(?:\.\d+)?", question)) >= 2 and bool(re.search(r"计算|多少|需要|抽取|稀释|换算|求|等于|[=×÷*/]", question))


def footnote(missing: list[str]) -> str:
    if not missing:
        return ""
    shown = ", ".join(missing[:8]) + (f" ({len(missing)} in all)" if len(missing) > 8 else "")
    return f"\n\n> ⚠ Citation check: these sources did not appear in this task's tool output and may come from the model's memory; verify them before use: {shown}"


NO_TOOLS_NOTE = ""  # no visible warning: the answer is shown as written


_HAS_SOURCE = re.compile(r"https?://|\bPMID\b|\bDOI\b|\bNCT\d{8}\b|\b10\.\d{4,9}/", re.I)


def has_identifiers(answer: str) -> bool:
    """The answer cites something checkable (PMID / DOI / trial number / address). Without a search these can only be remembered or made up."""
    c = cited(answer or "")
    return any(c.values())


# ---------------------------------------------------------------------------------------------- facts with no source behind them
# A sentence can state a date, a figure or a product code with no link at all. The model's own evidence (what the tools printed, what the
# searches returned, the commands it ran) is available as text, so the specific tokens of each sentence can be looked up in it.

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-/.年]\s*(\d{1,2})(?:\s*[-/.月]\s*(\d{1,2})\s*日?)?(?!\d)")
_DATE_EN = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})?,?\s*((?:19|20)\d{2})\b|\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+((?:19|20)\d{2})\b", re.I)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+\.\d+|\d{2,})(?![\w.]*\w)")  # 10 and up: a count, a residue, a position
_CODE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*-?\d{2,}[A-Za-z0-9]*\b")
_RANGE = re.compile(r"(?<![\w.])(\d+)\s*[–—\-~～]\s*(\d+)(?![\w.]*\w)")  # 1–61, 325–356: a span of residues, years or doses
_PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%")  # a percentage is a figure whatever its size
_IDS = re.compile(r"PMID[:：]?\s*\d+|\b10\.\d{4,9}/\S+|\bNCT\d{8}\b|https?://\S+|\b[\w.-]+\.(?:com|org|net|cn|gov|edu|io)(?:/\S*)?", re.I)
_EXAMPLE = ("例如", "比如", "举例", "示例", "譬如", "假设", "假如", "for example", "e.g.")  # an illustration is not a claim about the world
_THRESHOLDS = {"0.1", "0.05", "0.01", "0.001", "0.0001", "0.5"}  # conventional cut-offs, not findings
# Phrases by which the model itself marks a figure as unverified: the Chinese ones it writes in Chinese answers, the English ones in English.
_MARKED = ("未核实", "未经检索", "未取到", "没有取到", "无法核实", "未公开", "仅为推算", "估算", "约为推算",
           "unverified", "not retrieved", "could not verify", "not publicly available", "estimated", "not obtained")


_YMD = re.compile(r"year\W{1,12}value\W{1,12}((?:19|20)\d{2})\W{1,40}?month\W{1,12}value\W{1,12}(\d{1,2})(?:\W{1,40}?day\W{1,12}value\W{1,12}(\d{1,2}))?", re.I)


_COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")


def evidence_from_events(events: list[dict]) -> str:
    """What the model was shown, from a task's stored events: command output, and the search results (titles, addresses, snippets).

    Not the model's own queries and code, and not the event bookkeeping (timestamps, sequence numbers): a figure the model wrote into a query
    is not a source for it, and a timestamp is not a fact about the world."""
    parts: list[str] = []
    for e in events:
        kind = e.get("type")
        if kind == "observation":
            parts.append(str(e.get("text") or ""))
        elif kind == "tool":
            for r in e.get("results") or []:
                parts.append(" ".join(str(r.get(k) or "") for k in ("title", "domain", "url", "snippet")))
    return "\n".join(parts)


def _evidence_facts(evidence: str) -> tuple[set, set, str]:
    """(dates found as (y, m, d) and (y, m), the evidence with number separators removed, lowercased)."""
    dates: set[tuple] = set()
    for m in _DATE.finditer(evidence):
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        dates.add((y, mo))
        if d:
            dates.add((y, mo, int(d)))
    for m in _DATE_EN.finditer(evidence):
        if m.group(1):
            y, mo, d = int(m.group(3)), _MONTHS[m.group(1)[:3].lower()], m.group(2)
        else:
            y, mo, d = int(m.group(6)), _MONTHS[m.group(5)[:3].lower()], m.group(4)
        dates.add((y, mo))
        if d:
            dates.add((y, mo, int(d)))
    for m in _YMD.finditer(evidence):  # ORCID-style records: {'year': {'value': '2021'}, 'month': {'value': '06'}, 'day': {'value': '20'}}
        y, mo = int(m.group(1)), int(m.group(2))
        dates.add((y, mo))
        if m.group(3):
            dates.add((y, mo, int(m.group(3))))
    for m in _COMPACT_DATE.finditer(evidence):  # 20230224, as a table cell or a record writes it: the same day as 2023年2月24日
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dates.add((y, mo))
        dates.add((y, mo, d))
    plain = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", evidence).lower()
    return dates, plain


def _decimals_of(plain: str, cap: int = 60000) -> list[float]:
    """The decimal numbers in the evidence, for telling a rounded figure (0.8557 for 0.85570321) from an invented one."""
    out: list[float] = []
    for m in re.finditer(r"(?<![\w.])(\d+\.\d{2,})", plain):
        try:
            out.append(float(m.group(1)))
        except ValueError:
            continue
        if len(out) >= cap:
            break
    return out


def _number_backed(raw: str, plain: str, decimals: list[float]) -> bool:
    """The figure is in the evidence as written, or is that evidence rounded (also as a percentage)."""
    if re.search(r"(?<![\d.])" + re.escape(raw) + r"(?![\d])", plain):
        return True
    try:
        v = float(raw)
    except ValueError:
        return False
    places = len(raw.split(".")[1]) if "." in raw else 0
    tol = 0.5 * 10 ** -places + 1e-9
    return any(abs(x - v) <= tol or abs(x * 100 - v) <= tol for x in decimals)


def _range_backed(a: str, b: str, plain: str, window: int = 150) -> bool:
    """Both ends of a span are in the evidence, the second within a short distance after the first."""
    ends = re.compile(r"(?<![\d.])" + re.escape(a) + r"(?![\d])")
    second = re.compile(r"(?<![\d.])" + re.escape(b) + r"(?![\d])")
    for m in ends.finditer(plain):
        if second.search(plain, m.end(), m.end() + window):
            return True
    return False


def _segments(answer: str) -> list[str]:
    """Sentences and table rows of the answer, without code blocks."""
    text = re.sub(r"```.*?```", " ", answer or "", flags=re.S)
    out: list[str] = []
    for line in text.split(chr(10)):
        for part in re.split(r"(?<=[。！？!?；;])", line):
            part = part.strip()
            if len(part) >= 6:
                out.append(part)
    return out


_ORG = re.compile(r"[\u4e00-\u9fff]{2,8}(?:股份有限公司|有限责任公司|有限公司|生物科技|生物医药|生物技术|科技|大学|学院|研究所|研究院|医院|研究中心|中心|集团)")


def ungrounded(answer: str, evidence: str, limit: int = 12) -> list[dict]:
    """Sentences of `answer` with a specific date, figure or product code that appears nowhere in `evidence`.

    A marked sentence ("未核实", "未取到" ...) is the model being honest and is left alone; numbers below 100, bare years and the identifiers /
    addresses the citation check already covers are not looked at.
    """
    dates, plain = _evidence_facts(evidence or "")
    decimals = _decimals_of(plain)
    out: list[dict] = []
    for seg in _segments(answer):
        if any(w in seg for w in _MARKED) or any(w in seg.lower() for w in _EXAMPLE):
            continue
        body = _IDS.sub(" ", seg)
        missing: list[str] = []
        for m in _DATE.finditer(body):
            y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
            key = (y, mo, int(d)) if d else (y, mo)
            if key not in dates:
                missing.append(m.group(0).strip())
        body_nodate = _DATE.sub(" ", body)
        for m in _NUMBER.finditer(body_nodate):
            raw = m.group(1).replace(",", "")
            if re.fullmatch(r"(?:19|20)\d{2}", raw) or raw in _THRESHOLDS:
                continue
            if not _number_backed(raw, plain, decimals):
                missing.append(m.group(1))
        for m in _RANGE.finditer(body_nodate):  # both ends must be in the evidence, close together: "start 319 ... end 357" is a span, "319" alone is not
            a, b = m.group(1), m.group(2)
            if (re.fullmatch(r"(?:19|20)\d{2}", a) and re.fullmatch(r"(?:19|20)\d{2}", b)) or (len(a) < 2 and len(b) < 2):
                continue
            if not _range_backed(a, b, plain):
                missing.append(m.group(0).strip())
        for m in _PERCENT.finditer(body_nodate):
            if not _number_backed(m.group(1), plain, decimals):
                missing.append(m.group(0).strip())
        for m in _CODE.finditer(body_nodate):
            if m.group(0).lower() not in plain:
                missing.append(m.group(0))
        for m in _ORG.finditer(body_nodate):  # an organisation name written in Chinese: the output may give it in English only, so this asks for a check
            name = re.sub(r"^(?:经历包括|经历|包括|及|和|与|并|在|是|为|于|由|即|或|的)+", "", m.group(0))
            if name.lower() not in plain and re.sub(r"\s", "", name).lower() not in re.sub(r"\s", "", plain):
                missing.append(name + " (an organisation name; this Chinese form does not appear in the tool output)")
        if missing:
            spans = " ".join(x for x in missing if re.search(r"[–—\-~～]", x))  # a flagged span lists its ends once, not twice
            missing = [x for x in missing if not (re.fullmatch(r"\d+", x) and re.search(r"(?<!\d)" + x + r"(?!\d)", spans))]
            out.append({"text": seg[:90], "missing": list(dict.fromkeys(missing))[:5]})
        if len(out) >= limit:
            break
    return out


def ungrounded_note(items: list[dict]) -> str:
    if not items:
        return ""
    shown = "; ".join(f"“{i['text']}” ({', '.join(i['missing'])})" for i in items[:6])
    more = f" ({len(items)} in all)" if len(items) > 6 else ""
    return f"{chr(10) * 2}> ⚠ Unverified specifics: the dates, figures or identifiers below do not appear in this task's searches or tool output (they may be the model's estimate or come from memory); do not rely on them: {shown}{more}"


# ---- checking what the answer cites, without sending the model back --------------------------------------------------------------------

_EXISTS: dict[str, bool] = {}


def exists(display: str, timeout: float = 4.0) -> bool:
    """Does this cited address / PMID / DOI / registry number really exist? One quick request; a network failure counts as "not confirmed"."""
    if display in _EXISTS:
        return _EXISTS[display]
    import requests

    from biomni_ui import refs

    headers = {"User-Agent": "Mozilla/5.0 (biomni-lite source check)"}
    ok = False
    try:
        if display.startswith("PMID"):
            ident = re.sub(r"\D", "", display)
            ok = requests.get(f"https://pubmed.ncbi.nlm.nih.gov/{ident}/", headers=headers, timeout=timeout).status_code == 200
        elif display.startswith("DOI"):
            ident = display.split(" ", 1)[1]
            ok = requests.get(f"https://api.crossref.org/works/{ident}", headers=headers, timeout=timeout).status_code == 200
        elif display.startswith("NCT"):
            ok = requests.get(f"https://clinicaltrials.gov/api/v2/studies/{display.split()[-1]}", headers=headers, timeout=timeout).status_code == 200
        elif display.startswith("http"):
            from urllib.parse import urlparse

            if refs.is_public_host(urlparse(display).hostname or ""):
                r = requests.get(display, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
                ok = r.status_code < 400
                r.close()
    except Exception:
        ok = False
    _EXISTS[display] = ok
    return ok


def verify_sources(missing: list[str]) -> tuple[list[str], list[str]]:
    """Split cited sources that the tools never returned into (confirmed to exist, still unconfirmed). The checks run side by side."""
    if not missing:
        return [], []
    import threading

    results: dict[str, bool] = {}

    def work(m: str) -> None:
        results[m] = exists(m)

    threads = [threading.Thread(target=work, args=(m,), daemon=True) for m in missing[:12]]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    confirmed = [m for m in missing if results.get(m)]
    return confirmed, [m for m in missing if not results.get(m)]


def mark_specifics(answer: str, loose: list[dict]) -> str:
    """Put (unverified) right behind each date, figure or code that nothing in the task backs, so the reader sees which ones, with no second pass of the model."""
    done = 0
    for item in loose:
        seg = item.get("text") or ""
        for token in item.get("missing") or []:
            if done >= 10 or token not in answer or f"{token}(unverified)" in answer:
                continue
            pattern = r"(?<![\d.])" + re.escape(token) + r"(?![\d])"
            if seg and seg[:60] in answer:
                start = answer.index(seg[:60])
                m = re.compile(pattern).search(answer, start)
            else:
                m = re.compile(pattern).search(answer)
            if m is None:
                continue
            answer = answer[: m.end()] + "(unverified)" + answer[m.end():]
            done += 1
    return answer
