"""Scout: parallel first look before the agent starts.

The official app begins most tasks the same way: a literature/database search and a web search run side by side, and the
model reads both. The stock agent here starts blind: when a question holds a name it does not recognise (a company, a
product code, a person) it has to guess what it is, and often guesses wrong ("Example Bio" taken for a gene symbol).

A short model call looks at the question and picks up to four quick probes from a fixed list: web search for unfamiliar
names, plus the structured source that fits the domain (clinical trials, PubMed, Open Targets, UniProt, GEO, ChEMBL ...).
They run in parallel (a few seconds), and their results are handed to the agent as a starting point. The agent still
decides what to trust and what to do next; nothing here answers the question.
"""

from __future__ import annotations

import inspect
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable

from biomni_ui import dbtools, lit, web

MAX_PROBES = 4
PROBE_SECONDS = 25
RESULT_CHARS = 1600
DIGEST_CHARS = 7000

PROBES: dict[str, tuple[Callable[..., str], str]] = {
    "web_search": (web.web_search, "Web search (query): a company, product code, person or abbreviation you do not recognise, or the latest news. Use the name itself, with no extra words"),
    "clinical_trials": (dbtools.clinical_trials, "ClinicalTrials.gov registrations (condition = disease, intervention = intervention or drug; in English)"),
    "pubmed_search": (lit.pubmed_search, "PubMed literature (query, PubMed syntax, in English)"),
    "europepmc_search": (lit.europepmc_search, "Europe PMC including preprints (query, in English)"),
    "open_targets": (dbtools.open_targets, "Open Targets associations (query = gene or disease name, kind='target'|'disease')"),
    "uniprot_lookup": (dbtools.uniprot_lookup, "UniProt protein (query, e.g. gene_exact:TP53)"),
    "geo_search": (dbtools.geo_search, "GEO public datasets (query, in English)"),
    "chembl_target_compounds": (dbtools.chembl_target_compounds, "Active compounds for a ChEMBL target (target = gene or protein name)"),
    "fda_adverse_events": (dbtools.fda_adverse_events, "FAERS adverse events (drug = English generic name, in upper case)"),
    "reactome_pathways": (dbtools.reactome_pathways, "Reactome pathways (gene_or_term)"),
}

ROUTER_SYSTEM = (
    "You are the pre-search dispatcher for a research assistant. Before the agent starts work, you decide which quick probes to run in parallel, so that it has a reliable starting point. Output only JSON:\n"
    '{"skip": false, "why": "one sentence", "probes": [{"tool": "<name>", "args": {...}}]}\n'
    "Available probes (at most 4; argument names must match those below):\n" + "\n".join(f"- {k}: {v[1]}" for k, v in PROBES.items()) + "\n"
    "Rules:\n"
    "1. If the question contains a name you do not recognise or are unsure of (a company, product code, person, abbreviation, or a Chinese drug name), you must include web_search, with query set to that name itself (you may add one disambiguating word, e.g. \"Example Bio\").\n"
    "2. Then add the most suitable structured probe for the domain: clinical trials -> clinical_trials; target, gene or disease associations -> open_targets; protein -> uniprot_lookup; literature -> pubmed_search; public datasets -> geo_search; drug activity -> chembl_target_compounds. Use standard English names in English arguments.\n"
    "3. A product code or abbreviation (e.g. GC101, BD111) searched alone often hits unrelated things with the same name. The queries for pubmed_search, europepmc_search and clinical_trials must include disambiguating context (the company's English name, the disease, or the drug class). If you are not sure what it refers to, use only web_search and no literature probe.\n"
    "4. These are starting points, not answers. Do not pad the list to look thorough, and leave out anything you are unsure about.\n"
    "5. Pure calculation, small talk, translation or rewriting, or analysis of the user's own files or data (the agent must write its own code): set skip to true and leave probes empty."
)


def parse_plan(text: str) -> tuple[bool, str, list[dict[str, Any]]]:
    """(skip, why, probes) from the router's reply; unknown tools, bad arguments and duplicates are dropped."""
    try:
        a, b = text.find("{"), text.rfind("}") + 1
        data = json.loads(text[a:b])
    except (ValueError, TypeError):
        return True, "", []
    probes: list[dict[str, Any]] = []
    for item in data.get("probes") or []:
        tool, args = item.get("tool"), item.get("args") or {}
        if tool not in PROBES or not isinstance(args, dict):
            continue
        try:
            inspect.signature(PROBES[tool][0]).bind(**args)
        except TypeError:
            continue
        if any(isinstance(v, str) and not v.strip() for v in args.values()):
            continue
        if {"tool": tool, "args": args} not in probes:
            probes.append({"tool": tool, "args": args})
    return bool(data.get("skip")) or not probes, str(data.get("why") or ""), probes[:MAX_PROBES]


def _call(probe: dict[str, Any]) -> tuple[str, float]:
    t = time.time()
    try:
        out = PROBES[probe["tool"]][0](**probe["args"])
    except Exception as e:
        out = f"probe failed: {type(e).__name__}: {str(e)[:120]}"
    return str(out), time.time() - t


def label(probe: dict[str, Any]) -> str:
    return f"{probe['tool']}({', '.join(f'{k}={v!r}' for k, v in probe['args'].items())})"


def run(llm, question: str, today: str, emit: Callable[[dict[str, Any]], None] = lambda e: None) -> str:
    """The digest of what the probes found ("" when there is nothing to add). Never raises."""
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        reply = llm.invoke([SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=f"{today}\nQuestion: {question}")])
        skip, why, probes = parse_plan(reply.content if isinstance(reply.content, str) else str(reply.content))
    except Exception:
        return ""
    if skip:
        return ""
    emit({"type": "reasoning", "text": f"Running a few quick probes in parallel to give the analysis a reliable starting point: {why}" if why else "Running a few quick probes in parallel."})
    parts: list[str] = []
    pool = ThreadPoolExecutor(max_workers=len(probes))
    futures = [(p, pool.submit(_call, p)) for p in probes]
    deadline = time.time() + PROBE_SECONDS
    for p, fut in futures:
        try:
            out, secs = fut.result(timeout=max(0.1, deadline - time.time()))
        except FutureTimeout:
            out, secs = f"probe timed out (>{PROBE_SECONDS} s)", float(PROBE_SECONDS)
        emit({"type": "code", "language": "python", "code": label(p), "elapsed": round(secs, 2)})
        emit({"type": "observation", "text": out[:2500], "files": [], "elapsed": round(secs, 2)})
        if not out.startswith(("probe failed", "probe timed out")):
            parts.append(f"### {label(p)}\n{out[:RESULT_CHARS]}")
    pool.shutdown(wait=False)
    if not parts:
        return ""
    digest = "\n\n".join(parts)[:DIGEST_CHARS]
    return (
        "[Pre-search run by the system in parallel before you started (a starting point only)]\n"
        "The results below are the raw output of quick probes. Search summaries are not page text, and registry or database records must be checked. "
        "A hit on a code or abbreviation in the literature may be an unrelated thing with the same name, so confirm that it really mentions the company or product the user asked about before relying on it. First judge whether these are enough to answer, and what the name refers to. "
        "If they are not enough, go deeper with tools (read the source, try other search terms, query other databases). Do not treat these leads as the final answer, and do not give up just because they found nothing.\n\n" + digest
    )
