"""Fast literature tools, registered into the agent next to the stock ones without touching upstream code.

The stock `query_pubmed` goes through `pymed` (80 s for one search in our measurements) and prints only title, abstract
and journal, so the agent can neither say who wrote a paper nor give a PMID. The functions in `biomni_ui.lit` answer in
2-8 s and print PMID, authors, journal, year, DOI and (for authors) the affiliation printed on the paper.

Schemas are written by hand: `A1.add_tool` would ask the model to write them, which costs a model call per tool at
every start-up.
"""

from __future__ import annotations

from typing import Any

MODULE = "biomni_ui.lit"
WEB_MODULE = "biomni_ui.web"
REPORT_MODULE = "biomni_ui.report"


def _p(name: str, type_: str, description: str, default: Any = None) -> dict[str, Any]:
    return {"name": name, "type": type_, "description": description, "default": default}


SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "ena_run_table",
        "module": "biomni_ui.fetch_ngs",
        "description": "List the sequencing runs of a public ENA project, study or run accession with sample names, layout, size and FASTQ download commands. Does not download; use it to plan a fetch.",
        "required_parameters": [_p("accession", "str", "Project, study or run accession, e.g. PRJEB1787")],
        "optional_parameters": [_p("max_runs", "int", "How many runs to list (1-500)", 50)],
    },
    {
        "name": "tooluniverse_search",
        "module": "biomni_ui.tooluniverse_gateway",
        "description": "Search the ToolUniverse collection (about 200 loaded public tools: OpenTargets, PubChem, ChEMBL, FDA labels, Monarch and more) by keywords. Returns tool names with descriptions and required arguments.",
        "required_parameters": [_p("query", "str", "Keywords, e.g. drug label, pubchem, clinvar")],
        "optional_parameters": [_p("limit", "int", "How many to list (1-50)", 10)],
    },
    {
        "name": "tooluniverse_run",
        "module": "biomni_ui.tooluniverse_gateway",
        "description": "Run one ToolUniverse tool by its exact name (from tooluniverse_search) with its arguments; returns the JSON result.",
        "required_parameters": [_p("name", "str", "Exact tool name"), _p("arguments", "dict", "The tool's arguments as an object")],
        "optional_parameters": [],
    },
    {
        "name": "civic_gene_variants",
        "module": "biomni_ui.civic",
        "description": "CIViC curated cancer variant evidence for a gene: the gene summary, how many variants are curated, and the first variants with types. Use it for somatic variants in cancer.",
        "required_parameters": [_p("gene", "str", "Gene symbol, e.g. EGFR")],
        "optional_parameters": [_p("max_results", "int", "How many variants to list (1-100)", 20)],
    },
    {
        "name": "author_papers",
        "description": (
            "PREFERRED for 'find the papers of <person>'. Searches PubMed for one author (Chinese names are converted to pinyin, "
            "every plausible spelling is tried), keeps only papers whose author list really contains that person, and groups the "
            "result by the affiliation printed on each paper so namesakes can be told apart. Prints PMID, title, authors, "
            "journal, year, DOI and affiliation. Takes 2-8 s."
        ),
        "required_parameters": [_p("name", "str", "Author name, e.g. 'Wang Xiaoming', 'Li Xiaohua' or '王小明'")],
        "optional_parameters": [
            _p("affiliation", "str", "Institution keyword to narrow down (e.g. 'Tsinghua')", None),
            _p("orcid", "str", "ORCID of the person, the most reliable filter", None),
            _p("max_results", "int", "Maximum papers per spelling", 30),
            _p("max_groups", "int", "How many affiliation groups to list", 6),
            _p("per_group", "int", "Papers listed per group", 8),
            _p("compact", "bool", "One short line per paper (year | journal | title | PMID | DOI), for long lists", False),
        ],
    },
    {
        "name": "openalex_author_candidates",
        "description": "List OpenAlex author profiles for a name (institution, paper count, ORCID, topics) to decide which person is meant before searching their papers.",
        "required_parameters": [_p("name", "str", "Author name in any script")],
        "optional_parameters": [_p("limit", "int", "Number of candidates", 5)],
    },
    {
        "name": "pubmed_search",
        "description": (
            "PREFERRED PubMed search. Accepts PubMed query syntax (e.g. 'CAR-T[Title/Abstract] AND (\"2026/10/01\"[dp] : \"2026/10/29\"[dp])'), "
            "newest first. Prints PMID, title, authors, journal, year and DOI for every hit in 2-4 s. Use paper_abstracts for the abstracts."
        ),
        "required_parameters": [_p("query", "str", "PubMed query string")],
        "optional_parameters": [_p("max_results", "int", "Number of papers", 10)],
    },
    {
        "name": "paper_abstracts",
        "description": "Fetch abstract, authors, journal, year and DOI for PubMed IDs. Use it on the PMIDs returned by pubmed_search / author_papers / europepmc_search.",
        "required_parameters": [_p("pmids", "list[str] | str", "PMIDs as a list or a comma-separated string")],
        "optional_parameters": [],
    },
    {
        "name": "europepmc_search",
        "description": "Search Europe PMC, which covers PubMed and also preprints (bioRxiv, medRxiv, Research Square). Newest first; marks preprints as not peer reviewed.",
        "required_parameters": [_p("query", "str", "Europe PMC query")],
        "optional_parameters": [
            _p("max_results", "int", "Number of papers", 10),
            _p("since", "str", "Only papers first published on or after this ISO date, e.g. '2026-10-01'", None),
            _p("by_relevance", "bool", "Rank by how well each paper matches the query instead of newest first", False),
        ],
    },
    {
        "name": "web_search",
        "module": WEB_MODULE,
        "description": (
            "PREFERRED web search (works from this network, 1 s). Returns numbered results with title, site, link and snippet. "
            "Use it for companies, news, people, clinical-trial registries, patents and anything not in PubMed; then call read_webpage on the "
            "best links, because a snippet is not the page. Cite the links you actually used."
        ),
        "required_parameters": [_p("query", "str", "Search words; Chinese or English. Rare names work better with an extra word, e.g. company + product")],
        "optional_parameters": [
            _p("max_results", "int", "Number of results", 8),
            _p("language", "str", "'zh' or 'en' (only matters for the Bing fallback)", "zh"),
            _p("engine", "str", "'auto' (360 first, Bing as fallback), '360' or 'bing'", "auto"),
        ],
    },
    {
        "name": "read_webpage",
        "module": WEB_MODULE,
        "description": "Download a web page and return its title and main text (menus and scripts removed). Some sites (e.g. Baidu Baike) refuse downloads; then use another result.",
        "required_parameters": [_p("url", "str", "Page address")],
        "optional_parameters": [_p("max_chars", "int", "Maximum characters to return", 6000)],
    },
    {
        "name": "read_pdf",
        "module": WEB_MODULE,
        "description": (
            "Read a PDF from a link (prospectus, annual report, paper). Long files are searched page by page for the query words and the best pages "
            "come back with page numbers, so figures can be cited as 'p. 123'. Use it when a web page links to a filing (read_webpage lists such links)."
        ),
        "required_parameters": [_p("url", "str", "PDF address")],
        "optional_parameters": [
            _p("query", "str", "Words to look for, e.g. 'net loss, cash, redemption liabilities'; empty = first pages", ""),
            _p("max_chars", "int", "Maximum characters to return", 8000),
        ],
    },
    {
        "name": "deep_research",
        "module": "biomni_ui.research",
        "description": (
            "Multi-angle evidence gathering with source reading: plans up to 6 searches (web, PubMed, author profiles), runs them in parallel, reads the best pages "
            "and PDFs, checks gaps, and returns a written briefing whose claims carry links, PMIDs or DOIs (25-60 s). Use it for background on a company, person, "
            "clinical program, drug or topic when one search is not enough; verify key numbers yourself. Not for analysing data files."
        ),
        "required_parameters": [_p("question", "str", "The question, with names written out in full")],
        "optional_parameters": [_p("context", "str", "Earlier facts needed to understand the question (optional)", "")],
    },
    {
        "name": "clinical_lookup",
        "module": "biomni_ui.clinical",
        "description": (
            "PREFERRED for any question about clinical trials of a company, drug, gene or disease (10-40 s, one call). Searches ClinicalTrials.gov on sponsor, "
            "intervention, condition and free text; for a Chinese or unknown name it first finds out what the name is and which English names / product codes "
            "the registry uses, searches again, and looks for Chinese registry numbers. Returns a written summary with a table of trials."
        ),
        "required_parameters": [_p("question", "str", "The question as the user asked it, e.g. 'clinical trials of Example Bio'")],
        "optional_parameters": [],
    },
    {
        "name": "make_chart",
        "module": REPORT_MODULE,
        "description": "Draw a clean chart (bar, barh, line or pie; Chinese text works) and save it as a PNG for a report. Returns the file name. Call once per figure, with numbers that came from tool output.",
        "required_parameters": [
            _p("kind", "str", "'bar', 'barh', 'line' or 'pie'"),
            _p("labels", "list[str]", "Category or x-axis labels"),
            _p("values", "list[float] | dict[str, list[float]]", "One list, or {series name: list} for several series"),
        ],
        "optional_parameters": [
            _p("title", "str", "Chart title", ""),
            _p("filename", "str", "PNG file name", ""),
            _p("ylabel", "str", "Axis label with the unit", ""),
        ],
    },
    {
        "name": "make_deck",
        "module": REPORT_MODULE,
        "description": (
            "Build an editable PowerPoint deck (16:9, Chinese text works) and save it as .pptx. Each slide is {'heading', 'bullets': [...], 'table': [[header...], [row...]], "
            "'figure': 'chart.png', 'source': '...', 'notes': '...'}; all but heading optional. Put the source of every slide in 'source'. Returns the file name."
        ),
        "required_parameters": [
            _p("title", "str", "Deck title (cover slide)"),
            _p("slides", "list[dict]", "The content slides, in order"),
        ],
        "optional_parameters": [_p("filename", "str", "File name without extension", ""), _p("subtitle", "str", "Subtitle on the cover", "")],
    },
    {
        "name": "build_report",
        "module": REPORT_MODULE,
        "description": (
            "PREFERRED way to finish a deep task that asks for a report ('图文报告', '详细报告', 'report'): writes one self-contained HTML page "
            "(images embedded) plus a Markdown copy, which the Results panel shows. Sections can hold text, a table (first row = header) and a figure "
            "from make_chart. List every source used in `sources`."
        ),
        "required_parameters": [
            _p("title", "str", "Report title"),
            _p("summary", "str", "3-5 sentence conclusion"),
            _p("sections", "list[dict]", "Each {'heading': str, 'text': str, 'table': [[header...], [row...]], 'figure': 'chart.png', 'caption': str}; all but heading optional"),
        ],
        "optional_parameters": [
            _p("filename", "str", "File name without extension", ""),
            _p("sources", "list[str]", "Source lines, e.g. 'PMID: 123 | title' or a URL", None),
        ],
    },
]


DB_MODULE = "biomni_ui.dbtools"
DB_TOOLS = ["clinical_trials", "fda_adverse_events", "chembl_target_compounds", "open_targets", "target_tractability", "uniprot_lookup",
            "gtex_expression", "gnomad_constraint", "geo_search", "string_interactions", "reactome_pathways",
            "ensembl_gene", "pdb_structures", "alphafold_structure", "pubchem_compound", "openalex_works"]
DB_PARAMS = {
    "uniprot": "UniProt accession, e.g. 'P04637'", "name": "Compound name in English, e.g. 'aspirin'",
    "condition": "Disease or condition, e.g. 'beta thalassemia'", "intervention": "Drug or intervention words, e.g. 'gene therapy' (optional)",
    "status": "Registry status such as RECRUITING, COMPLETED (optional)", "drug": "Drug generic name in English, e.g. 'PEMBROLIZUMAB'",
    "target": "Gene or protein name, e.g. 'EGFR'", "query": "Gene symbol or disease name (for open_targets) / search words (uniprot, geo)",
    "kind": "'disease' = targets associated with that disease; 'target' = diseases associated with that gene", "gene": "Human gene symbol, e.g. 'TP53'",
    "gene_or_term": "Gene symbol or pathway words", "max_results": "How many rows", "top": "How many rows", "limit": "How many rows",
    "standard_type": "Potency type: IC50, Ki, EC50", "entry_type": "gse = series, gds = curated dataset", "species": "NCBI taxon id, 9606 = human",
}


def _db_schemas() -> list[dict[str, Any]]:
    """Schemas for the database tools, derived from the functions themselves so signature and description cannot drift."""
    import importlib
    import inspect

    mod = importlib.import_module(DB_MODULE)
    out = []
    for name in DB_TOOLS:
        fn = getattr(mod, name)
        req, opt = [], []
        for p in inspect.signature(fn).parameters.values():
            hint = "int" if p.annotation in (int, "int") else "str"
            entry = _p(p.name, hint, DB_PARAMS.get(p.name, p.name), None if p.default is inspect.Parameter.empty else p.default)
            (req if p.default is inspect.Parameter.empty else opt).append(entry)
        doc = " ".join((inspect.getdoc(fn) or "").split())
        out.append({"name": name, "module": DB_MODULE, "description": "Database tool (a fast direct call, 1-3 s). " + doc, "required_parameters": req, "optional_parameters": opt})
    return out


SCHEMAS += _db_schemas()


def register(agent: Any) -> list[str]:
    """Add the tools to `agent` (registry, prompt listing, code namespace). Safe to call twice. Returns the tool names."""
    import builtins

    import importlib

    done = []
    for template in SCHEMAS:
        schema = {"module": MODULE, **template}
        name = schema["name"]
        fn = getattr(importlib.import_module(schema["module"]), name)
        if agent.tool_registry.get_tool_by_name(name) is None:
            agent.tool_registry.register_tool(dict(schema))
        bucket = agent.module2api.setdefault(schema["module"], [])
        if not any(t.get("name") == name for t in bucket):
            bucket.append(dict(schema))
        if not hasattr(agent, "_custom_functions"):
            agent._custom_functions = {}
        agent._custom_functions[name] = fn
        if not hasattr(agent, "_custom_tools"):
            agent._custom_tools = {}
        agent._custom_tools[name] = {"name": name, "description": schema["description"], "module": schema["module"]}
        if not hasattr(builtins, "_biomni_custom_functions"):
            builtins._biomni_custom_functions = {}
        builtins._biomni_custom_functions[name] = fn
        done.append(name)
    # one prompt rebuild for all of them, and the retriever's document table needs the new rows
    import pandas as pd

    reg = agent.tool_registry
    reg.document_df = pd.DataFrame([[int(i), reg.get_tool_by_id(int(i))] for i in range(len(reg.tools))], columns=["docid", "document_content"])
    agent.configure()
    return done


def route_tool_llm(factory) -> list[str]:
    """Make the stock `query_*` and genomics tools call OUR model object instead of upstream's get_llm.

    Those tools ask a model to turn the question into a request URL. Upstream's get_llm would build its own client from
    default_config (for the Codex source: the slow command-line wrapper), so they are pointed at the same direct,
    effort-aware model the rest of the app uses. Only the module attribute is replaced; no upstream file is edited.
    """
    import importlib

    done = []
    for name in ("biomni.tool.database", "biomni.tool.genomics"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        if hasattr(mod, "get_llm"):
            mod.get_llm = lambda *a, **k: factory()
            done.append(name)
    from biomni_ui import query_fixes

    query_fixes.LLM_FACTORY = factory
    done += query_fixes.install()
    return done
