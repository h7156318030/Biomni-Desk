"""Clinical-trial lookups that do not depend on the model's luck.

A question like "Example Bio clinical trials" needs four small decisions: what the name is (company, drug, gene, disease), which
registry field to search (sponsor / intervention / condition / free text), what the registry calls it (a Chinese company
name returns nothing on ClinicalTrials.gov), and which records really belong to it. The general agent got these wrong
often (one failed lookup, then "please give me the gene symbol"). Here code makes every one of them in the same order each
time and the model only writes the summary from the records.

Steps: 1) search ClinicalTrials.gov directly on all four fields; 2) if nothing, web-search the name, let a short model call
list English names / product codes from the results; 3) search again with those; 4) look for Chinese registry numbers (CTR);
5) fetch the details of every distinct trial.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from biomni_ui import lit, web

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ("NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName,Condition,InterventionName,EnrollmentCount,StartDate,PrimaryCompletionDate,"
          "WhyStopped,HasResults,PrimaryOutcomeMeasure,OfficialTitle")
_TRIAL_WORDS = re.compile(r"临床试验|临床研究|临床进展|临床管线|管线|登记|试验登记|clinical\s+trials?|\bNCT\d{8}\b|\btrials?\b", re.IGNORECASE)
_NOT_THIS = re.compile(r"分析|画|绘|文件|csv|差异表达|生存|引物|序列|代码|论文|文献|作者|综述", re.IGNORECASE)


def wants_clinical(prompt: str) -> bool:
    """Short, plain "trials of X" questions. Anything that asks for analysis, papers or code goes to the agent."""
    p = (prompt or "").strip()
    return 4 <= len(p) <= 90 and bool(_TRIAL_WORDS.search(p)) and not _NOT_THIS.search(p)


def subject_of(prompt: str) -> str:
    """The name the question is about: the prompt without the trial words and filler."""
    s = _TRIAL_WORDS.sub(" ", prompt)
    s = re.sub(r"^(?:请|帮我|麻烦)?\s*(?:查询|查一下|查找|查|搜索|搜|看看|了解一下|了解|有哪些|有什么|列出)\s*", "", s.strip())
    s = re.sub(r"有哪些|有哪几个|有哪几项|有没有|有无|情况|进展|最新|目前|现在", " ", s)
    s = re.sub(r"[的了吗呢？?。.!！,，、]+", " ", s)
    s = re.sub(r"\b(?:the|of|for|in|on|a|an|and)\b", " ", s, flags=re.IGNORECASE)
    return " ".join(s.split())


def _search(params: dict[str, Any]) -> list[dict[str, Any]]:
    data = lit._json(API, params={**params, "pageSize": 30, "format": "json", "fields": FIELDS})
    return data.get("studies", [])


LAST_ERROR = [""]  # why the latest failed search failed (shown next to a failed step)


class RegistryUnavailable(RuntimeError):
    """ClinicalTrials.gov did not answer any of the searches: that is not the same as "no trials"."""


def _search_retry(params: dict[str, Any]) -> list[dict[str, Any]]:
    """One field search; a failed request is tried again (with a pause) before it counts as failed."""
    last: Exception | None = None
    for attempt in range(3):
        try:
            return _search(params)
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    status = getattr(getattr(last, "response", None), "status_code", None)
    raise RuntimeError(f"HTTP {status}" if status else f"{type(last).__name__}: {str(last)[:100]}")


def search_checked(name: str) -> tuple[list[dict[str, Any]], int]:
    """(distinct trials, number of the four field searches that failed). A failed search is not an empty one."""
    jobs = [{"query.term": name}, {"query.spons": name}, {"query.intr": name}, {"query.cond": name}]

    def one(p: dict[str, Any]):
        try:
            return _search_retry(p), ""
        except Exception as e:
            return [], str(e)

    seen: dict[str, dict[str, Any]] = {}
    failed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res, err in pool.map(one, jobs):
            if err:
                failed += 1
                LAST_ERROR[0] = err
            for s in res:
                nct = s["protocolSection"]["identificationModule"]["nctId"]
                seen.setdefault(nct, s)
    return list(seen.values()), failed


def search_all_fields(name: str) -> list[dict[str, Any]]:
    """The same name tried as free text, sponsor, intervention and condition; distinct trials only."""
    return search_checked(name)[0]


def summarise(s: dict[str, Any]) -> dict[str, Any]:
    p = s["protocolSection"]
    ident, st, des = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
    return {
        "nct": ident.get("nctId"), "title": ident.get("briefTitle", ""), "official": ident.get("officialTitle", ""),
        "phase": "/".join(des.get("phases") or []) or "N/A", "status": st.get("overallStatus", ""),
        "why_stopped": st.get("whyStopped", ""), "sponsor": (p.get("sponsorCollaboratorsModule", {}).get("leadSponsor") or {}).get("name", ""),
        "conditions": (p.get("conditionsModule", {}).get("conditions") or [])[:3],
        "interventions": [i.get("name", "") for i in (p.get("armsInterventionsModule", {}).get("interventions") or [])][:3],
        "enrollment": (des.get("enrollmentInfo") or {}).get("count"), "start": (st.get("startDateStruct") or {}).get("date", ""),
        "primary_completion": (st.get("primaryCompletionDateStruct") or {}).get("date", ""),
        "primary_outcome": ((p.get("outcomesModule", {}).get("primaryOutcomes") or [{}])[0]).get("measure", ""),
        "has_results": bool(s.get("hasResults")),
    }


ALIAS_SYSTEM = (
    "You are a drug development intelligence assistant. The user gave you a name. Say what it refers to, and list the English forms it may take on ClinicalTrials.gov.\n"
    "Output only JSON: {\"kind\":\"company|drug|gene|disease|combo|other\",\"what\":\"one sentence on what it is\",\"aliases\":[\"at most 8 search terms\"]}\n"
    "Rules:\n"
    "- Generic drug names, disease names, gene symbols and technical terms: translate them into standard English with your own medical knowledge (for example 帕博利珠单抗 -> pembrolizumab; 肝癌 -> hepatocellular carcinoma).\n"
    "- English names and former names of a company: use those that appear in the search results first. A name you genuinely know (for example 示例生物 = Example Bio) may also be written. They are only search terms; the answer comes only from the registration records.\n"
    "- Codes of products in development (for example BD111, GC101): write only those that really appear in the search results. Do not invent them from memory.\n"
    "- If the name is a combination such as \"drug + disease\", give one Essie expression in addition to each English name, for example: pembrolizumab AND hepatocellular carcinoma.\n"
    "- If you are not sure, write less rather than padding the list."
)



def resolve_aliases(llm, name: str, web_text: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        reply = llm.invoke([SystemMessage(content=ALIAS_SYSTEM), HumanMessage(content=f"Name: {name}\n\nSearch results:\n{web_text[:6000]}")])
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        a, b = text.find("{"), text.rfind("}") + 1
        data = json.loads(text[a:b])
    except Exception:
        return {"kind": "other", "what": "", "aliases": []}
    data["aliases"] = [x for x in dict.fromkeys(str(x).strip() for x in data.get("aliases", [])) if x][:6]
    return data


def ctr_numbers(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bCTR\d{8,}\b|\bCXSL\d{7,}\b|\bCXHL\d{7,}\b|\bCXSS\d{7,}\b", text)))


def gather(question: str, llm, emit: Callable[[dict[str, Any]], None] = lambda e: None) -> dict[str, Any]:
    """Everything the summary is written from. Emits one code/observation pair per step so the page shows what was done."""
    import time

    name = subject_of(question) or question

    def step(code: str, fn: Callable[[], str]) -> str:
        t = time.time()
        out = fn()
        secs = round(time.time() - t, 2)
        emit({"type": "code", "language": "python", "code": code, "elapsed": secs})
        emit({"type": "observation", "text": out, "files": [], "elapsed": secs})
        return out

    found: dict[str, list[dict[str, Any]]] = {}  # query -> distinct trials it found
    failed: dict[str, int] = {}  # query -> how many of its four field searches got no answer from the registry

    def run_query(q: str) -> None:
        hits, bad = search_checked(q)
        found[q] = [summarise(s) for s in hits]
        failed[q] = bad

        def text() -> str:
            if bad == 4 and not found[q]:
                return f"{q}: search failed (ClinicalTrials.gov did not respond: {LAST_ERROR[0]}; retried 3 times), so this is not \"0 trials\""
            note = f" ({bad} field searches failed; the results may be incomplete)" if bad else ""
            return f"{q}: {len(found[q])} registrations matched{note}" + "".join(f"\n{t['nct']} | {t['title'][:80]}" for t in found[q][:5])

        step(f'search_all_fields("{q}")', text)

    run_query(name)
    info: dict[str, Any] = {"kind": "other", "what": "", "aliases": []}
    web_text = ""
    if not found[name] or re.search(r"[一-鿿]", name):
        # a Chinese name matches nothing in an English registry: find out what it is and what the registry calls it
        # (the plain name only: extra words drag the search engine towards unrelated pages)
        web_text = step(f'web_search("{name}")', lambda: web.web_search(name, 8))
        info = resolve_aliases(llm, name, web_text)
        step(f'resolve_aliases("{name}")', lambda: f"{info.get('what', '')} (type: {info.get('kind')}); English names / codes: {', '.join(info['aliases']) or 'none'}")
        for alias in info["aliases"]:
            if alias not in found:
                run_query(alias)
    ctr_text = ""
    if re.search(r"[一-鿿]", name) or info["aliases"]:
        ctr_text = step(f'web_search("{name} 临床试验 登记号")', lambda: web.web_search(f"{name} 临床试验 登记号", 6))

    if failed and all(n == 4 for n in failed.values()) and not any(found.values()):
        raise RegistryUnavailable("ClinicalTrials.gov did not respond")
    # the most specific set wins: "drug AND condition" hits are what was asked for; the drug alone is just context
    combos = [q for q in found if " AND " in q and found[q]]
    if combos:
        chosen = {t["nct"]: t for q in combos for t in found[q]}
        scope = f"Only registrations matching all of {' / '.join(combos)} are listed; {len({t['nct'] for ts in found.values() for t in ts} - set(chosen))} more broader registrations, found by searching the drug or disease alone, are not listed."
    else:
        chosen = {t["nct"]: t for ts in found.values() for t in ts}
        scope = "All registrations matched by any search term are listed (duplicates removed)."
    trials = list(chosen.values())
    for t in trials:  # keep the material small enough that no trial is cut off
        t.pop("official", None)
        t["primary_outcome"] = (t.get("primary_outcome") or "")[:100]
    return {"name": name, "info": info, "scope": scope, "total": len(trials), "trials": trials[:45], "queries": {q: len(v) for q, v in found.items()}, "failed_queries": [q for q, n in failed.items() if n],
            "ctr": ctr_numbers(web_text + "\n" + ctr_text), "web": web_text[:2500], "ctr_web": ctr_text[:1800]}


WRITE_SYSTEM = (
    "You are a rigorous clinical research intelligence assistant. Answer only from the material below; write nothing that is not in it. Requirements:\n"
    "0. The material's scope says which part of the registrations is listed, and total is the overall count. State this accurately; do not say \"none\" unless total is 0.\n"
    "0b. failed_queries in the material are search terms that got no response from the registry. Their results are incomplete or unknown, and must never be written as \"0 trials / no registrations\". Name the search terms that did not respond, and suggest retrying later.\n"
    "1. The first paragraph says directly: what the name refers to (company, drug, gene or disease); how many registrations ClinicalTrials.gov holds, and in which phases and statuses.\n"
    "2. List every registration in a Markdown table: registry number (as a link, https://clinicaltrials.gov/study/NCT number) | study | phase | status | sponsor | enrolment | start date. Include the reason for stopping where the status has one.\n"
    "3. Distinguish registration information from trial results. Mark separately the trials with results (has_results). Do not treat a registration as evidence of efficacy.\n"
    "4. If the material contains Chinese registry numbers (CTR/CXSL and so on), list them and state that they come from web search summaries and were not checked on the registry platform.\n"
    "5. If the sponsor name differs from the company name the user asked about, write \"the registered sponsor is X; whether it is the same legal entity is not verified\".\n"
    "6. End with a limitation: only ClinicalTrials.gov and web search were checked, and the Chinese registry platform was not logged into to check each entry; give the query date.\n"
    "If there are no registrations at all, say so honestly and list the names and fields you tried. Reply in the user's language, and do not paste code."
)



def write(llm, question: str, today: str, data: dict[str, Any]) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    body = json.dumps({k: data[k] for k in ("name", "info", "scope", "total", "queries", "failed_queries", "trials", "ctr", "ctr_web")}, ensure_ascii=False)[:30000]
    reply = llm.invoke([SystemMessage(content=WRITE_SYSTEM), HumanMessage(content=f"{today}\nQuestion: {question}\n\nMaterial:\n{body}")])
    return (reply.content if isinstance(reply.content, str) else str(reply.content)).strip()


def run(llm, fast, question: str, today: str, emit: Callable[[dict[str, Any]], None]) -> str:
    data = gather(question, fast or llm, emit)
    return write(llm, question, today, data)


# ---- as a tool for the agent ------------------------------------------------------------------------------------

def clinical_lookup(question: str) -> str:
    """All registered clinical trials for a company, drug, gene or disease name, in one reliable call (10-40 s).

    Searches ClinicalTrials.gov on sponsor, intervention, condition and free text; when the name is Chinese or unknown it first
    finds out what the name is and which English names / product codes the registry uses, searches again with those, and looks
    for Chinese registry numbers. Returns a written summary with a table of trials. Prefer it to calling clinical_trials by hand.
    """
    from biomni_ui import research
    from biomni_ui.runner import today_line

    if not research.BOUND["llm"]:
        return "clinical_lookup has no model bound yet (it has to be started through the workbench)."
    llm = research.BOUND["llm"]()
    fast = research.BOUND["fast"]() if research.BOUND["fast"] else None
    return run(llm, fast, question, today_line(), lambda ev: None)


from biomni_ui import connectors as _connectors  # noqa: E402
_connectors.guard(globals())  # the switch of each database connector is checked on every call
