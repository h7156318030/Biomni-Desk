"""Research lane: plan several searches, run them in parallel, read the best pages, then write one cited answer.

Measured on this machine, the agent loop answered "who is X / what did company Y do lately" after ONE search and no page
reading, in 50-75 s, and often said it could not confirm. The official app searches from several angles, reads the
sources and cross-checks before writing. This lane does the same with two model calls (plan, write) and a few seconds
of parallel tool time, and shows every search and page as a step the user can open.
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from biomni_ui import lit, web

MAX_QUERIES = 6
MAX_PAGES = 6
PAGE_CHARS = 3500
SEARCH_CHARS = 3000
AUTHOR_CHARS = 16000

# The lane exists for ONE job the stock agent does badly: "who is this author and which papers are theirs" (namesakes, ORCID,
# preprints). Company, clinical, gene, disease, analysis and design questions all go to the agent with its full toolset.
_AUTHOR_LOOKUP = re.compile(
    r"(?:查询|查找|检索|搜索|查|找|搜|看看|列出|给我)\s*(?:一下)?\s*(?P<n1>[一-鿿·]{2,4}|[A-Za-z][A-Za-z.\-]+(?:\s+[A-Za-z][A-Za-z.\-]+){1,3})\s*(?:的|所有的|全部的)?\s*(?:论文|文章|发表|文献|著作)"
    r"|(?P<n2>[一-鿿·]{2,4}|[A-Za-z][A-Za-z.\-]+(?:\s+[A-Za-z][A-Za-z.\-]+){1,3})\s*(?:的)?(?:论文列表|发表了什么|发表过什么|都发表了)"
    r"|papers?\s+(?:by|of)\s+[A-Za-z]|publications?\s+(?:by|of)\s+[A-Za-z]",
    re.IGNORECASE,
)
# A Chinese personal name starts with a family name; this keeps "本月发表的…文献" or "最近的论文" from being read as a person.
_SURNAMES = ("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
             "凌欧阳司马上官诸葛东方皇甫尉迟公孙慕容令狐司徒夏侯")


def _is_name(name: str) -> bool:
    return not re.search(r"[一-鿿]", name) or name[0] in _SURNAMES


_NOT_AUTHOR = re.compile(r"关于|主题|综述|研究进展|最新进展|机制|基因|蛋白|疾病|药物|靶点|通路|治疗|疫苗|公司|企业|机构", re.IGNORECASE)
# Work that needs the agent's own code or the user's files: never taken by this lane.
_NEEDS_AGENT = re.compile(
    r"上传|附件|文件|csv|xlsx|h5ad|fasta|fastq|代码|脚本|运行|画|绘|作图|图表|序列|blast|比对|基因表达|差异表达|富集|聚类|单细胞|数据集|"
    r"upload|attachment|\bfiles?\b|\bcode\b|script|\brun\b|\bplot|\bchart|figure|sequence|alignment|gene expression|differential expression|enrich|cluster|single[- ]cell|dataset|"
    r"计算|模拟|预测|设计.*(引物|sgrna|蛋白|分子)|@|download|下载|calculat|simulat|predict|\bdesign.*(primer|sgrna|protein|molecul)|\bmy (?:file|data)",
    re.IGNORECASE,
)

PLAN_SYSTEM = (
    "You are a research assistant planning the searches for a question. Output one JSON object and no other text:\n"
    '{"queries":[{"tool":"web"|"pubmed"|"author","q":"search terms"}],"note":"one sentence on how you plan to search, in the user\'s language"}\n'
    "Rules:\n"
    f"- At most {MAX_QUERIES} queries: one from each different angle, with no repeats.\n"
    "- web = web search (companies, news, people's home pages, institutions, clinical trial registries, policy). For obscure names add a qualifier, for example \"company name + product or field\". Search the English and the Chinese name as separate queries if both exist.\n"
    "- pubmed = PubMed syntax search for academic literature (you may use [Title/Abstract] and date ranges such as (\"2026/01/01\"[dp] : \"2026/12/31\"[dp])).\n"
    "- author = search papers by author. Write the person's name in q (Chinese name or pinyin). Always also add one web query to find this person's institution and research field, to tell apart people with the same name.\n"
    "- Replace \"he / she / it / this company\" in the question with the concrete name from the context given below.\n"
    "- Search terms may use only the question itself and facts confirmed in the context. The research fields and institutions in the \"user background\" may be used only for ranking; never put them into search terms, which would skew the results.\n"
    "- For author searches, the author tool searches PubMed, ORCID, Semantic Scholar, Zenodo and OpenAlex at once. Web queries use the person's name alone (for example \"Xiaohua Li\" with publications / ORCID / Zenodo), with no other words."
)

WRITE_SYSTEM = (
    "You are a rigorous biomedical research assistant. Write the answer only from the \"search material\" below. Do not write anything the material does not contain, and do not fill gaps from memory.\n"
    "Requirements:\n"
    "1. The first paragraph gives the conclusion directly (no more than 3 sentences).\n"
    "2. \"## Key findings\": one sentence per item, followed at the end by its source, written as [title or site](URL), or PMID: number, DOI. Cite only URLs, PMIDs and DOIs that really appear in the material.\n"
    "3. For author searches: first decide from the web material (official home pages, news) the person's institution and field. Then list, as a Markdown table, every paper whose institution matches (year | journal | title | PMID/DOI | verdict). Verdicts are \"confirmed / highly likely / to be checked\", each with its basis (institution, co-authors, research field). If a person has changed institution, and co-authors (the author list) or topics in other institution groups repeat confirmed papers, mark them \"highly likely\". Records of unrelated people with the same name are summarised in a sentence or two, not listed one by one. Do not drop matching papers just because there are many.\n"
    "3b. When the name is ambiguous (the material splits papers among several \"possible people\", and the web pages give no anchor to say which one): do not mix everyone's papers into one table. First explain in two or three sentences that this name corresponds to several different researchers. Then give a small table of the largest candidates (no. | institution | field, summarised from journals and titles | number of papers | year range | frequent co-authors). Use the research field, institution and ORCID in the \"user background\" to say which one is most likely and why, and list a paper table for that one only (two at most); the rest get one line each. End by asking the user for the institution, research field or ORCID to settle it. The ORCID, institution and topics of OpenAlex candidates can serve as anchors, but their author profiles may also merge different people; say so.\n"
    "3a. ORCID is the strongest evidence of identity: in an ORCID record, the \"works listed by the person\" and the \"employment\" belong to the same person. Papers from PubMed clusters, OpenAlex profiles and Zenodo archives that match these works, or whose institution matches, are all merged into this person. Companies or institutions named in the employment record (for example Shanghai ExampleBio) must be named, because they explain why the person writes both physics preprints and gene therapy papers. Same-name people unrelated to the ORCID works get one line in the candidate table.\n"
    "3d. Rank candidates by the amount of evidence: profiles with an ORCID, the most works and continuous years come first. The \"user background\" is only a weak hint (it may be incomplete or out of date); use it to order candidates only when the evidence is comparable, and never let it push a candidate with more evidence down or exclude it. An OpenAlex profile with an ORCID and many works is a strong candidate: it must come first in the candidate table, with its works listed (the main types, which are preprints, and which have not been peer reviewed). People in PubMed clusters and OpenAlex profiles may or may not be the same person; compare year, institution and co-authors before saying so.\n"
    "3c. Be concise: the whole answer should be about 1,800 words or fewer. In the \"verdict\" column write only \"confirmed / highly likely / to be checked\", plus a basis of no more than 15 words (for example \"listed by the person on ORCID\"). A journal paper table has at most 25 rows. The list table for Zenodo and other preprint archives is appended automatically by the system at the end of the answer, so do not write that table yourself; in the body use one or two sentences to say how many there are, the main topics, and that none has been peer reviewed.\n"
    "3e. The \"journal\" column of the paper table takes the journal name given after the title in the material's line; PMID and DOI come from the material's line. Where the material really gives no value, write \"—\", not \"not provided\" or \"not listed in the material\". \"Confirmed\" means only that the paper is listed in this person's own ORCID record (self-reported, not a check against the original paper); say what this means in one sentence above the table.\n"
    "3f. Source credibility, highest first: the person's own ORCID record and employment > the institution printed on the paper (the PubMed author field, the \"affiliation of this paper\" in OpenAlex works) > Semantic Scholar > the summary information in an OpenAlex profile. The \"most recent institution\" and \"number of papers\" in an OpenAlex profile are algorithmic merges that often combine different people with the same name. When you see a note that the affiliations are inconsistent, judge each paper by its own affiliation, and treat papers that do not match the ORCID employment as another person with the same name. Do not treat the profile as one person, and do not use its summary to overturn ORCID.\n"
    "4. Where sources contradict each other, or you have only a search summary and did not read the original, mark it \"summary only\" or \"sources disagree\".\n"
    "5. Use a Markdown table whenever there are numbers or comparisons.\n"
    "6. The last section, \"## Methods and limitations\": state which search queries and pages you used, the search date (use the given today's date), what is still missing, and what could be searched next.\n"
    "Reply in the user's language. Do not write process narration such as \"I will ...\", and do not paste code."
)

_SKIP_HOSTS = ("bilibili", "douyin", "iqiyi", "youku", "haokan", "tieba", "zhidao.baidu", "baike.baidu", "map.", "fanyi.", "ai.so.com")


def wants_research(prompt: str) -> bool:
    """True only for "find the papers of <a person>": the one job this lane does better than the general agent."""
    p = (prompt or "").strip()
    if not (4 <= len(p) <= 200) or os.environ.get("BIOMNI_UI_RESEARCH", "1") == "0":
        return False
    m = _AUTHOR_LOOKUP.search(p)
    if not m or _NEEDS_AGENT.search(p):
        return False
    name = m.group("n1") or m.group("n2") or ""
    return _is_name(name) and not _NOT_AUTHOR.search(p.replace(name, ""))


def _json_object(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def plan(llm, question: str, today: str, context: str) -> tuple[list[dict[str, str]], str]:
    from langchain_core.messages import HumanMessage, SystemMessage

    user = (f"Earlier context (to resolve pronouns):\n{context}\n\n" if context else "") + f"{today}\nQuestion: {question}"
    try:
        reply = llm.invoke([SystemMessage(content=PLAN_SYSTEM), HumanMessage(content=user)])
        data = _json_object(reply.content if isinstance(reply.content, str) else str(reply.content)) or {}
    except Exception:
        data = {}
    qs = []
    for item in data.get("queries") or []:
        tool, q = str(item.get("tool", "web")).lower(), " ".join(str(item.get("q", "")).split())
        aff = " ".join(str(item.get("aff", "") or "").split())
        if q and tool in ("web", "pubmed", "author") and (tool, q, aff) not in [(x["tool"], x["q"], x.get("aff", "")) for x in qs]:
            qs.append({"tool": tool, "q": q, **({"aff": aff} if aff else {})})
    if not qs:  # the model gave nothing usable: search the question itself
        qs = [{"tool": "web", "q": question}]
    return qs[:MAX_QUERIES], str(data.get("note") or "I search from several angles, read the most relevant pages, then answer.")


REFINE_SYSTEM = (
    "You are a research assistant. Below is the summary of the first round of searches. Decide whether key gaps remain; you may schedule at most 3 more searches. If the material is already sufficient, return {\"queries\":[]}.\n"
    "Output only JSON: {\"queries\":[{\"tool\":\"web\"|\"pubmed\"|\"author\",\"q\":\"…\",\"aff\":\"optional, for author only: English institution keywords\"}],\"note\":\"one sentence, in the user's language\"}\n"
    "Common gaps:\n"
    "- Author searches: the web pages show the person's institutions, former institutions and co-authors. Many older papers give only \"surname + initial\" (for example Wang X), which strict matching in the first round misses. Use the author tool to search again: put the name in q, and in aff put English keywords for every institution in the web pages (including former ones), separated by |, for example Shanghai Jiao Tong | Aarhus University. With aff, older papers that give only \"surname + initial\" are accepted.\n"
    "- Companies or events: try the name in another form (English name, short name), or check the original announcement or registry page for the key figures.\n"
    "Do not repeat what the first round already searched."
)


def refine(llm, question: str, today: str, digest: str) -> tuple[list[dict[str, str]], str]:
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        reply = llm.invoke([SystemMessage(content=REFINE_SYSTEM), HumanMessage(content=f"{today}\nQuestion: {question}\n\nSummary of the first round:\n{digest}")])
        data = _json_object(reply.content if isinstance(reply.content, str) else str(reply.content)) or {}
    except Exception:
        return [], ""
    out = []
    for item in data.get("queries") or []:
        tool, q = str(item.get("tool", "web")).lower(), " ".join(str(item.get("q", "")).split())
        aff = " ".join(str(item.get("aff", "") or "").split())
        if q and tool in ("web", "pubmed", "author"):
            out.append({"tool": tool, "q": q, **({"aff": aff} if aff else {})})
    return out[:3], str(data.get("note") or "")


def step_label(q: dict[str, str]) -> str:
    kind = {"web": "Web search", "pubmed": "PubMed search", "author": "Author search (PubMed, ORCID, Zenodo, OpenAlex)"}.get(q["tool"], q["tool"])
    return f"{kind}: {q['q']}" + (f" (limited to institution {q['aff']})" if q.get("aff") else "")


def _run_query(item: dict[str, str]) -> tuple[str, str, float]:
    t = time.time()
    tool, q = item["tool"], item["q"]
    try:
        if tool == "pubmed":
            code, out = f'pubmed_search("{q}", 10)', lit.pubmed_search(q, 10)
        elif tool == "author":
            aff = item.get("aff") or None
            cjk = "".join(re.findall(r"[一-鿿·]+", q))
            q = cjk or q  # a mixed "王小明 Wang Xiaoming" is searched as the Chinese name (it also covers the pinyin spelling)
            code = f'author_papers("{q}", affiliation="{aff}", compact=True)' if aff else f'author_papers("{q}", compact=True)'
            with ThreadPoolExecutor(max_workers=3) as pool:  # PubMed, ORCID/Zenodo/Semantic Scholar and OpenAlex are independent
                papers = pool.submit(lit.author_papers, q, aff, None, 30, 12, 40, True)
                ident, oa = pool.submit(lit.identity_sources, q), pool.submit(lit.openalex_profile, q, 1)
                parts = []
                for job in (ident, papers, oa):
                    try:
                        parts.append(job.result())
                    except Exception:
                        pass
                out = "\n\n".join(parts) or "Search failed: the author search returned no content"
        else:
            code, out = f'web_search("{q}", 8)', web.web_search(q, 8)
    except Exception as e:
        code, out = f'{tool}("{q}")', f"Search failed: {type(e).__name__}: {e}"
    return code, out, time.time() - t


def anchors_of(queries: list[dict[str, str]]) -> list[str]:
    """The name(s) a result must mention to be worth reading: words of the author queries (Latin words and Chinese runs)."""
    words: list[str] = []
    for q in queries:
        if q["tool"] == "author":
            words += [w.lower() for w in re.findall(r"[A-Za-z]{3,}|[一-鿿]{2,}", q["q"])]
    return list(dict.fromkeys(words))


def _relevant(block: str, needles: list[str] | None) -> bool:
    low = block.lower()
    return not needles or all(n in low for n in needles)  # a name is several words: "hao" alone matches half the web


def pick_pages(outputs: list[str], limit: int = MAX_PAGES, needles: list[str] | None = None) -> list[str]:
    """The best distinct addresses across all web searches: rank 1 of every query first, then rank 2, and so on.

    With `needles` (an author's name), a result is only read when its title or snippet mentions one of them: a page
    that does not even mention the person cannot help, and reading it costs seconds and pollutes the material.
    """
    per_query = []
    for o in outputs:
        blocks = re.findall(r"^\[\d+\] .*?\n\s+(https?://\S+)\n(.*)$", o, flags=re.M)
        titles = re.findall(r"^\[\d+\] (.*?)$", o, flags=re.M)
        per_query.append([u for (u, snippet), t in zip(blocks, titles) if _relevant(f"{t} {snippet} {u}", needles)])
    chosen: list[str] = []
    seen_hosts: dict[str, int] = {}
    for rank in range(8):
        for urls in per_query:
            if rank >= len(urls) or urls[rank] in chosen:
                continue
            u = urls[rank]
            host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
            if any(s in host for s in _SKIP_HOSTS) or u.lower().endswith((".pdf", ".jpg", ".png")) or seen_hosts.get(host, 0) >= 2:
                continue
            seen_hosts[host] = seen_hosts.get(host, 0) + 1
            chosen.append(u)
            if len(chosen) >= limit:
                return chosen
    return chosen


def _read(url: str) -> tuple[str, str, float]:
    t = time.time()
    try:
        return f'read_webpage("{url}")', web.read_webpage(url, PAGE_CHARS), time.time() - t
    except Exception as e:
        return f'read_webpage("{url}")', f"Could not read: {type(e).__name__}: {e}", time.time() - t


def zenodo_table(material: str, limit: int = 40) -> str:
    """The Zenodo deposits found for the person, as a table built by code (typing 30 rows costs the model ~20 s)."""
    m = re.search(r"### Zenodo[^\n]*\n(.*?)(?:\n\n###|\Z)", material, flags=re.S)
    if not m:
        return ""
    rows = []
    for line in m.group(1).splitlines():
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) >= 3 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]) and parts[2].startswith("DOI "):
            doi = parts[2][4:]
            rows.append(f"| {parts[0]} | {parts[1]} | [{doi}](https://doi.org/{doi}) |")
    if not rows:
        return ""
    more = f"\n\n({len(rows)} items in all; only the latest {limit} are listed)" if len(rows) > limit else ""
    return ("## Zenodo archive (preprints and reports, **not peer reviewed**, newest first; this table is generated by the program from the Zenodo records)\n\n| Date | Title | DOI |\n|---|---|---|\n"
            + "\n".join(rows[:limit]) + more)


def pick_pdfs(outputs: list[str], limit: int = 2) -> list[str]:
    """PDF addresses that appear in search results or in the 'PDF links' list of a page that was read."""
    found: list[str] = []
    for o in outputs:
        for u in re.findall(r"https?://[^\s)\]>\"']+", o):
            u = u.rstrip(".,;")
            if u.lower().split("?")[0].endswith(".pdf") and u not in found:
                found.append(u)
    # filings and papers first: they hold the numbers
    found.sort(key=lambda u: 0 if re.search(r"hkexnews|sse\.com|szse|cninfo|prospectus|zhaogu|annual|arxiv|biorxiv|ncbi", u, re.I) else 1)
    return found[:limit]


def _read_pdf(url: str, question: str) -> tuple[str, str, float]:
    t = time.time()
    terms = " ".join(web._terms(question)[:8])
    try:
        out = web.read_pdf(url, terms, 6000)
    except Exception as e:
        out = f"Could not read: {type(e).__name__}: {e}"
    if out.startswith("Could not read the PDF"):
        out = "Could not read: " + out
    return f'read_pdf("{url}", "{terms}")', out, time.time() - t


def write(llm, question: str, today: str, context: str, material: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    user = (f"Earlier context:\n{context}\n\n" if context else "") + f"{today}\nQuestion: {question}\n\nSearch material:\n{material}"
    reply = llm.invoke([SystemMessage(content=WRITE_SYSTEM), HumanMessage(content=user)])
    return (reply.content if isinstance(reply.content, str) else str(reply.content)).strip()


def run(llm, question: str, today: str, context: str, emit: Callable[[dict[str, Any]], None], cancelled: Callable[[], bool] = lambda: False, info: dict[str, Any] | None = None, fast=None) -> str | None:
    """Do the research, emitting step events as work finishes. Returns the answer, or None to hand the task to the agent."""
    fast = fast or llm  # planning and gap-finding are short JSON jobs: a low-effort model call is enough and 3x quicker
    steps = ["Plan which sources to check"]

    def mark(done: int) -> None:  # this lane bypasses the agent, so it must publish its own checklist (the To-do panel reads it)
        emit({"type": "plan", "steps": [{"text": t, "status": "done" if i < done else "todo"} for i, t in enumerate(steps)]})

    mark(0)
    queries, note = plan(fast, question, today, context)
    steps[:] = (["Plan which sources to check"] + [step_label(q) for q in queries]
                + ["Read the most relevant pages and PDFs (only those that mention this person)", "Check the gaps and search further if needed", "Merge the same person's papers and write the answer with sources"])
    mark(1)
    emit({"type": "reasoning", "text": note})
    if cancelled():
        return None
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        results = list(pool.map(_run_query, queries))
    for code, out, secs in results:
        emit({"type": "code", "language": "python", "code": code, "elapsed": round(secs, 2)})
        emit({"type": "observation", "text": out, "files": [], "elapsed": round(secs, 2)})
    web_outputs = [o for (c, o, _), q in zip(results, queries) if q["tool"] == "web"]
    mark(1 + len(queries))
    needles = anchors_of(queries)
    urls = pick_pages(web_outputs, needles=needles)
    pages: list[tuple[str, str, float]] = []
    if urls and not cancelled():
        emit({"type": "reasoning", "text": f"Reading the {len(urls)} most relevant pages to check the details."})
        with ThreadPoolExecutor(max_workers=len(urls)) as pool:
            pages = list(pool.map(_read, urls))
        for code, out, secs in pages:
            emit({"type": "code", "language": "python", "code": code, "elapsed": round(secs, 2)})
            emit({"type": "observation", "text": out[:1800], "files": [], "elapsed": round(secs, 2)})
    # PDFs only from material that is about the person/subject: a filing linked from an unrelated page is noise
    pdf_urls = pick_pdfs([o for (_, o, _) in pages if _relevant(o, needles)] + ([] if needles else [o for (_, o, _) in results]))
    pdfs: list[tuple[str, str, float]] = []
    if pdf_urls and not cancelled():
        emit({"type": "reasoning", "text": f"Found {len(pdf_urls)} PDFs (announcements, prospectuses, papers); reading the pages most relevant to the question's keywords."})
        with ThreadPoolExecutor(max_workers=len(pdf_urls)) as pool:
            pdfs = list(pool.map(lambda u: _read_pdf(u, question), pdf_urls))
        for code, out, secs in pdfs:
            emit({"type": "code", "language": "python", "code": code, "elapsed": round(secs, 2)})
            emit({"type": "observation", "text": out[:1800], "files": [], "elapsed": round(secs, 2)})
    digest_parts = [f"[{c}] {o[:500]}" for (c, o, _) in results] + [f"[{c}] {o[:600]}" for (c, o, _) in pages + pdfs if not o.startswith("Could not read")]
    mark(2 + len(queries))
    anchored = any("works listed by the person" in o for (_, o, _) in results)  # an ORCID record already settled who is who
    more, note2 = ([], "") if (cancelled() or anchored) else refine(fast, question, today, "\n\n".join(digest_parts)[:9000])
    if more:
        emit({"type": "reasoning", "text": note2 or "The first round left gaps; searching further."})
        with ThreadPoolExecutor(max_workers=len(more)) as pool:
            extra = list(pool.map(_run_query, more))
        for code, out, secs in extra:
            emit({"type": "code", "language": "python", "code": code, "elapsed": round(secs, 2)})
            emit({"type": "observation", "text": out, "files": [], "elapsed": round(secs, 2)})
        results += extra
        queries += more
    mark(3 + len(queries))
    useful = [r for r in results if not r[1].startswith(("Web search returned no results", "Search failed", "PubMed found no results"))]
    if not useful or cancelled():
        return None
    parts = []
    for (code, out, _), q in zip(results, queries):
        parts.append(f"### {code}\n{out[:AUTHOR_CHARS if q['tool'] == 'author' else SEARCH_CHARS]}")
    for code, out, _ in pages:
        if not out.startswith("Could not read"):
            parts.append(f"### {code}\n{out}")
    for code, out, _ in pdfs:
        if not out.startswith("Could not read"):
            parts.append(f"### {code}\n{out}")
    material = "\n\n".join(parts)
    if info is not None:
        info["material"] = material
    text = write(llm, question, today, context, material)
    mark(len(steps))
    table = zenodo_table(material)
    return text + ("\n\n" + table if table and "## Zenodo" not in text else "")


_REPORT_ASK = re.compile(r"报告|图文|report", re.IGNORECASE)


def wants_report(prompt: str) -> bool:
    return bool(_REPORT_ASK.search(prompt or ""))


def report_from_answer(question: str, answer: str, material_urls: list[str], charts: list[dict[str, Any]] | None = None) -> tuple[str, str]:
    """(code shown in the step card, printed result): the answer, split at its '## ' headings, as an illustrated report file."""
    from biomni_ui import report

    head, *chunks = re.split(r"^## +", answer, flags=re.M)
    sections = []
    for c in chunks:
        title, _, body = c.partition("\n")
        sections.append({"heading": title.strip(), "text": body.strip()})
    summary = " ".join(head.split())[:600] or question
    title = re.sub(r"^(请|麻烦|帮我|给我|我想要|我需要)+(一份|一个)?", "", re.sub(r"[？?。！!]+$", "", question))[:40]
    sources = list(dict.fromkeys(material_urls))
    for c in charts or []:
        sections.insert(0, {"heading": c["title"] or "figure", "figure": c["file"], "caption": f"{c['title']} ({c['unit']}); source: {c['source']}"})
    msg = report.build_report(title, summary, sections, sources=sources)
    return f'build_report("{title}", sections=[{len(sections)} sections], sources=[{len(sources)} items])', msg


CHART_SYSTEM = (
    "You are a data-organising assistant. From the \"search material\", pick at most three sets of data worth charting (the same indicator over several periods, or the same indicator compared across several objects). Output only JSON:\n"
    '{"charts":[{"kind":"bar"|"line"|"pie"|"barh","title":"use the conclusion as the title","labels":["…"],"values":[numbers],"unit":"unit","source":"data source (URL or PDF page)"}]}\n'
    "Rules: every number must appear exactly as written in the material (find the original figure in the material before converting units; do not estimate, and do not fill in missing periods). At least 2 data points. "
    "The title states the conclusion, not \"some chart\". If the material has no data worth charting, return {\"charts\":[]}."
)


def extract_charts(llm, question: str, answer: str, material: str) -> list[dict[str, Any]]:
    """Chart specs whose numbers can all be found in the material (a model's guess never reaches a figure)."""
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        reply = llm.invoke([SystemMessage(content=CHART_SYSTEM), HumanMessage(content=f"Question: {question}\n\nAnswer:\n{answer[:3000]}\n\nSearch material:\n{material[:24000]}")])
        data = _json_object(reply.content if isinstance(reply.content, str) else str(reply.content)) or {}
    except Exception:
        return []
    flat = material.replace(",", "").replace("，", "")
    good = []
    for c in data.get("charts") or []:
        try:
            labels, values = [str(x) for x in c["labels"]], [float(v) for v in c["values"]]
        except (KeyError, TypeError, ValueError):
            continue
        if len(labels) != len(values) or len(values) < 2 or c.get("kind") not in ("bar", "barh", "line", "pie"):
            continue
        if all(_in_text(v, flat) for v in values):
            good.append({"kind": c["kind"], "title": str(c.get("title", ""))[:60], "labels": labels, "values": values, "unit": str(c.get("unit", "")), "source": str(c.get("source", ""))})
    return good[:3]


def _in_text(v: float, text: str) -> bool:
    forms = {f"{v:g}", f"{v:.1f}", f"{v:.2f}", f"{v:,.0f}".replace(",", ""), str(int(v)) if v == int(v) else f"{v}"}
    return any(f and re.search(rf"(?<![\d.]){re.escape(f)}(?![\d])", text) for f in forms)


# ---- the same pipeline as a tool the agent can choose to call ---------------------------------------------------------

BOUND: dict[str, Any] = {"llm": None, "fast": None}


def bind(llm_factory: Callable[[], Any], fast_factory: Callable[[], Any] | None = None) -> None:
    """The server hands over the model factories; `deep_research` then runs inside the agent's own code step."""
    BOUND["llm"], BOUND["fast"] = llm_factory, fast_factory


def deep_research(question: str, context: str = "") -> str:
    """Gather evidence for a question from several angles and return a written, cited briefing (25-60 s).

    Plans up to 6 searches (web, PubMed, author profiles), runs them in parallel, reads the best pages and PDFs, checks gaps,
    and writes an answer whose claims carry links, PMIDs or DOIs. Use it for background on a company, person, clinical program,
    drug or topic, then verify key numbers yourself. It is not for analysing data files.
    """
    if not BOUND["llm"]:
        return "deep_research has no model bound yet (it has to be started through the workbench)."
    from biomni_ui.runner import today_line

    llm = BOUND["llm"]()
    fast = BOUND["fast"]() if BOUND["fast"] else None
    answer = run(llm, question, today_line(), context, lambda ev: None, lambda: False, None, fast)
    return answer or "No material was found to answer this question (the searches came back empty or were rate-limited). Try other keywords or another tool."
