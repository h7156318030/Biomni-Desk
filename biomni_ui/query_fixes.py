"""Working replacements for two stock tools whose upstream code cannot run, installed over the module attributes at start-up.

- `query_gnomad`: the natural-language branch never assigns `description` (UnboundLocalError), and the gene-symbol branch
  uses `gnomad_schema` without loading it (NameError).
- `query_geo`: its prompt contains unescaped braces, and `str.format` raises KeyError('"search_term"') before any request.

The function names, parameters and return shape ({"success", "query_info", "result"}) are kept, so the agent's existing
tool descriptions and code keep working. Upstream files are not edited; see `fast_tools.route_tool_llm`.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import requests

from biomni_ui import dbtools, lit

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "biomni" / "tool" / "schema_db"
LLM_FACTORY: Any = None  # set by fast_tools.route_tool_llm


def _ask_json(system: str, prompt: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    if LLM_FACTORY is None:
        raise RuntimeError("no model configured for tool queries")
    text = LLM_FACTORY().invoke([SystemMessage(content=system), HumanMessage(content=prompt)]).content
    text = text if isinstance(text, str) else str(text)
    a, b = text.find("{"), text.rfind("}") + 1
    return json.loads(text[a:b] if a >= 0 and b > a else text)


GEO_SYSTEM = (
    "You turn a biology question into one NCBI GEO (db=gds) search. Reply with ONLY a JSON object: "
    '{"search_term": "...", "description": "..."}. Syntax: terms joined with AND/OR; tags in brackets: '
    "gse[Entry Type] (series), gsm[Entry Type] (sample), Homo sapiens[Organism], Mus musculus[Organism], 2020:2026[Publication Date], "
    '"expression profiling by high throughput sequencing"[DataSet Type]. Prefer gse[Entry Type]. Keep the free-text terms few and specific.'
)


def query_geo(prompt=None, search_term=None, max_results=3):
    """Query the NCBI Gene Expression Omnibus (GEO) using natural language or a direct search term.

    Parameters
    ----------
    prompt (str, required): Natural language query about RNA-seq, microarray, or other expression data
    search_term (str, optional): Direct search term in GEO syntax
    max_results (int): Maximum number of results to return
    """
    if not prompt and not search_term:
        return {"error": "Either a prompt or a search term must be provided"}
    description = f"GEO search: {search_term}"
    if prompt and not search_term:
        try:
            q = _ask_json(GEO_SYSTEM, prompt)
        except Exception as e:
            return {"success": False, "error": f"Failed to build the GEO query: {type(e).__name__}: {str(e)[:120]}"}
        search_term, description = q.get("search_term", ""), q.get("description", "") or description
        if not search_term:
            return {"success": False, "error": "The model returned no search term", "raw_response": q}
    try:
        ids = lit._json(lit.EUTILS + "esearch.fcgi", params={"db": "gds", "term": search_term, "retmax": max_results, "retmode": "json"})["esearchresult"]
        records = []
        if ids["idlist"]:
            summ = lit._json(lit.EUTILS + "esummary.fcgi", params={"db": "gds", "id": ",".join(ids["idlist"]), "retmode": "json"})["result"]
            for uid in ids["idlist"]:
                s = summ.get(uid, {})
                records.append({k: s.get(k) for k in ("accession", "title", "summary", "taxon", "gdstype", "n_samples", "pdat", "ftplink")})
    except Exception as e:
        return {"success": False, "error": f"GEO request failed: {type(e).__name__}: {str(e)[:120]}"}
    return {"success": True, "query_info": {"search_term": search_term, "database": "gds", "description": description, "total": ids.get("count")}, "result": records}


def query_gnomad(prompt=None, gene_symbol=None, verbose=True):
    """Query gnomAD for variants in a gene using natural language or direct gene symbol.

    Parameters
    ----------
    prompt (str, required): Natural language query about genetic variants
    gene_symbol (str, optional): Gene symbol (e.g., "BRCA1")
    verbose (bool): Kept for compatibility

    Returns a dict with the GraphQL result (gene constraint, or whatever the question asked for).
    """
    if prompt is None and gene_symbol is None:
        return {"error": "Either a prompt or a gene_symbol must be provided"}
    queries = {}
    try:
        queries = pickle.loads((SCHEMA_DIR / "gnomad.pkl").read_bytes()).get("queries", {})
    except Exception:
        pass
    variables: dict[str, Any] = {}
    if gene_symbol and not prompt:
        query_str, variables, description = queries.get("gene_constraint", ""), {"g": gene_symbol}, f"gnomAD gene constraint for {gene_symbol}"
    else:
        system = ("You write one gnomAD GraphQL query (https://gnomad.broadinstitute.org/api). Reply with ONLY JSON: "
                  '{"query": "<GraphQL text>", "variables": {...}, "description": "..."}. Use only these known queries and fields, filling in the variables:\n'
                  + json.dumps(queries, ensure_ascii=False) + "\nReference genome GRCh38; datasets gnomad_r4 or gnomad_r2_1; variant ids look like 17-7675088-C-T.")
        try:
            q = _ask_json(system, prompt or "")
        except Exception as e:
            return {"success": False, "error": f"Failed to build the gnomAD query: {type(e).__name__}: {str(e)[:120]}"}
        query_str, variables, description = q.get("query", ""), q.get("variables") or {}, q.get("description", "gnomAD query")
    if not query_str:
        return {"success": False, "error": "No GraphQL query could be built"}
    try:
        r = requests.post("https://gnomad.broadinstitute.org/api", json={"query": query_str, "variables": variables}, headers={**lit.UA, "Accept": "application/json"}, timeout=40)
        body = r.json()
    except Exception as e:
        return {"success": False, "error": f"gnomAD request failed: {type(e).__name__}: {str(e)[:120]}"}
    if body.get("errors"):
        return {"success": False, "error": "gnomAD rejected the query: " + str(body["errors"][0].get("message"))[:200], "query_info": {"query": query_str, "variables": variables}}
    return {"success": True, "query_info": {"description": description, "query": query_str, "variables": variables}, "result": body.get("data")}


def install() -> list[str]:
    """Replace the two broken functions in biomni.tool.database (the agent imports them from there when it runs code)."""
    import importlib

    db = importlib.import_module("biomni.tool.database")
    db.query_geo, db.query_gnomad = query_geo, query_gnomad
    return ["query_geo", "query_gnomad"]


__all__ = ["query_geo", "query_gnomad", "install", "dbtools"]
