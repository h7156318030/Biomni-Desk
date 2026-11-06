"""Fast database tools for the agent: one call, one compact answer, 1-3 seconds each.

They back the data-centred official skills (clinical trials, targets, drugs, safety, expression, constraint, datasets,
interactions). The stock `biomni.tool.database` functions go through an LLM to build each query and are slow; these
call the public REST/GraphQL interfaces directly and print a fixed layout that the answer can cite.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from biomni_ui import lit

TIMEOUT = 25


def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        r = requests.post(url, json=body, headers={**lit.UA, "Accept": "application/json"}, timeout=TIMEOUT)
    except requests.RequestException:
        with requests.Session() as s:
            s.trust_env = False
            r = s.post(url, json=body, headers={**lit.UA, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _fail(what: str, e: Exception) -> str:
    return f"{what.strip()} query failed: {type(e).__name__}: {str(e)[:160]}"


# ---- ClinicalTrials.gov -----------------------------------------------------------------------------------------

def clinical_trials(condition: str, intervention: str = "", status: str = "", max_results: int = 15) -> str:
    """Registered trials from ClinicalTrials.gov: NCT id | title | phase | status | sponsor | start | enrollment."""
    params: dict[str, Any] = {"query.cond": condition, "pageSize": max_results, "format": "json", "countTotal": "true"}
    if intervention:
        params["query.intr"] = intervention
    if status:
        params["filter.overallStatus"] = status.upper().replace(" ", "_")
    try:
        data = lit._json("https://clinicaltrials.gov/api/v2/studies", params=params)
    except Exception as e:
        return _fail("ClinicalTrials.gov ", e)
    rows = []
    for s in data.get("studies", []):
        p = s.get("protocolSection", {})
        ident, st, des = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
        sponsor = (p.get("sponsorCollaboratorsModule", {}).get("leadSponsor") or {}).get("name", "")
        rows.append(f"{ident.get('nctId')} | {(ident.get('briefTitle') or '')[:110]} | {'/'.join(des.get('phases') or []) or '—'} | {st.get('overallStatus', '')} | {sponsor[:40]} | "
                    f"{(st.get('startDateStruct') or {}).get('date', '—')} | enrolled {(des.get('enrollmentInfo') or {}).get('count', '—')}")
    if not rows:
        return f"ClinicalTrials.gov found nothing: condition={condition} intervention={intervention}"
    return f"ClinicalTrials.gov: {data.get('totalCount', len(rows))} studies in all, first {len(rows)} listed (condition: {condition}; intervention: {intervention or 'any'}):\n" + "\n".join(rows)


# ---- openFDA adverse events -------------------------------------------------------------------------------------

def fda_adverse_events(drug: str, top: int = 15) -> str:
    """Most reported adverse reactions for a drug in FDA FAERS (openFDA), with counts. Reports are spontaneous: they show
    what is reported, not incidence or causality."""
    try:
        data = lit._json("https://api.fda.gov/drug/event.json", params={"search": f'patient.drug.medicinalproduct:"{drug}"', "count": "patient.reaction.reactionmeddrapt.exact", "limit": top})
        total = lit._json("https://api.fda.gov/drug/event.json", params={"search": f'patient.drug.medicinalproduct:"{drug}"', "limit": 1}).get("meta", {}).get("results", {}).get("total")
    except Exception as e:
        return _fail("openFDA ", e)
    rows = [f"{r['term']} | {r['count']}" for r in data.get("results", [])]
    if not rows:
        return f"openFDA has no adverse event reports for {drug} (the name must match the FAERS registered name; try the English generic name in capitals)."
    return f"openFDA FAERS: {drug}, {total} reports in all; most frequent reactions (MedDRA term | reports). These are spontaneous reports and do not establish incidence or causation:\n" + "\n".join(rows)


# ---- ChEMBL -----------------------------------------------------------------------------------------------------

def chembl_target_compounds(target: str, max_results: int = 15, standard_type: str = "IC50") -> str:
    """Most potent measured compounds for a target in ChEMBL (human single-protein targets): molecule | value nM | assay type | SMILES."""
    try:
        found = lit._json("https://www.ebi.ac.uk/chembl/api/data/target/search.json", params={"q": target, "limit": 10}).get("targets", [])
        pick = next((t for t in found if t.get("target_type") == "SINGLE PROTEIN" and t.get("organism") == "Homo sapiens"), None)
        if not pick:
            return f"ChEMBL has no human single-protein target for {target}. Candidates: " + "; ".join(f"{t.get('pref_name')}({t.get('target_chembl_id')},{t.get('organism')})" for t in found[:5])
        tid = pick["target_chembl_id"]
        acts = lit._json("https://www.ebi.ac.uk/chembl/api/data/activity.json", params={"target_chembl_id": tid, "standard_type": standard_type, "standard_units": "nM",
                                                                                          "standard_relation": "=", "limit": 200, "order_by": "standard_value"}).get("activities", [])
    except Exception as e:
        return _fail("ChEMBL ", e)
    seen, rows = set(), []
    for a in acts:
        mid = a.get("molecule_chembl_id")
        if not mid or mid in seen or a.get("standard_value") is None or float(a["standard_value"]) < 0.01:  # < 0.01 nM is almost always a unit error in the source
            continue
        seen.add(mid)
        rows.append(f"{a.get('molecule_pref_name') or mid} ({mid}) | {standard_type} {float(a['standard_value']):.3g} nM | {a.get('assay_type')} | {(a.get('canonical_smiles') or '')[:90]}")
        if len(rows) >= max_results:
            break
    return f"ChEMBL target {pick['pref_name']} ({tid}): compounds ranked by {standard_type}, strongest first (de-duplicated, exact values only, unit nM):\n" + "\n".join(rows)


# ---- Open Targets -----------------------------------------------------------------------------------------------

OT = "https://api.platform.opentargets.org/api/v4/graphql"


def open_targets(query: str, kind: str = "disease", top: int = 15) -> str:
    """Open Targets associations. kind='disease': the targets most associated with that disease; kind='target': the
    diseases most associated with that gene. Scores are 0-1 overall association scores."""
    try:
        hit = _post(OT, {"query": "query($q:String!,$e:[String!]){search(queryString:$q,entityNames:$e,page:{index:0,size:1}){hits{id name entity}}}",
                         "variables": {"q": query, "e": ["disease" if kind == "disease" else "target"]}})["data"]["search"]["hits"]
        if not hit:
            return f"Open Targets found no {kind}: {query}"
        h = hit[0]
        if kind == "disease":
            q = "query($id:String!,$n:Int!){disease(efoId:$id){name associatedTargets(page:{index:0,size:$n}){count rows{score target{approvedSymbol approvedName}}}}}"
            d = _post(OT, {"query": q, "variables": {"id": h["id"], "n": top}})["data"]["disease"]
            rows = [f"{r['target']['approvedSymbol']} | {r['target']['approvedName'][:60]} | {r['score']:.3f}" for r in d["associatedTargets"]["rows"]]
            return f"Open Targets: disease {d['name']} ({h['id']}) has {d['associatedTargets']['count']} associated targets; first {len(rows)} (gene | name | overall score):\n" + "\n".join(rows)
        q = "query($id:String!,$n:Int!){target(ensemblId:$id){approvedSymbol approvedName associatedDiseases(page:{index:0,size:$n}){count rows{score disease{name}}}}}"
        d = _post(OT, {"query": q, "variables": {"id": h["id"], "n": top}})["data"]["target"]
        rows = [f"{r['disease']['name'][:70]} | {r['score']:.3f}" for r in d["associatedDiseases"]["rows"]]
        return f"Open Targets: target {d['approvedSymbol']} ({d['approvedName']}, {h['id']}) has {d['associatedDiseases']['count']} associated diseases; first {len(rows)} (disease | overall score):\n" + "\n".join(rows)
    except Exception as e:
        return _fail("Open Targets ", e)


def target_tractability(gene: str) -> str:
    """Open Targets tractability flags for a human gene (small molecule / antibody / PROTAC / other), plus known-drug count."""
    try:
        hit = _post(OT, {"query": 'query($q:String!){search(queryString:$q,entityNames:["target"],page:{index:0,size:1}){hits{id name}}}', "variables": {"q": gene}})["data"]["search"]["hits"]
        if not hit:
            return f"Open Targets found no target {gene}"
        q = "query($id:String!){target(ensemblId:$id){approvedSymbol approvedName tractability{label modality value} drugAndClinicalCandidates{count}}}"
        d = _post(OT, {"query": q, "variables": {"id": hit[0]["id"]}})["data"]["target"]
    except Exception as e:
        return _fail("Open Targets ", e)
    by: dict[str, list[str]] = {}
    for t in d.get("tractability") or []:
        if t["value"]:
            by.setdefault(t["modality"], []).append(t["label"])
    lines = [f"Target {d['approvedSymbol']} ({d['approvedName']}): known drugs/clinical candidates {((d.get('drugAndClinicalCandidates') or {}).get('count'))}"]
    names = {"SM": "small molecule", "AB": "antibody", "PR": "PROTAC", "OC": "other modality"}
    for m, labels in by.items():
        lines.append(f"{names.get(m, m)}: {'; '.join(labels)}")
    if len(lines) == 1:
        lines.append("No modality is marked as druggable (evidence is insufficient, which is not the same as undruggable).")
    return "\n".join(lines)


# ---- UniProt ----------------------------------------------------------------------------------------------------

def uniprot_lookup(query: str, max_results: int = 5) -> str:
    """UniProtKB (reviewed human entries first): accession | gene | protein | length | function."""
    try:
        data = lit._json("https://rest.uniprot.org/uniprotkb/search", params={"query": f"({query}) AND reviewed:true AND organism_id:9606", "format": "json", "size": max_results,
                                                                                "fields": "accession,gene_names,protein_name,length,cc_function"})
    except Exception as e:
        return _fail("UniProt ", e)
    rows = []
    for r in data.get("results", []):
        gene = ((r.get("genes") or [{}])[0].get("geneName") or {}).get("value", "")
        name = (((r.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}).get("value", "")
        fn = next((t["value"] for c in r.get("comments", []) if c.get("commentType") == "FUNCTION" for t in c.get("texts", [])), "")
        rows.append(f"{r['primaryAccession']} | {gene} | {name} | {r.get('sequence', {}).get('length')} aa | {fn[:240]}")
    return "\n".join(rows) or f"UniProt found no reviewed human entry: {query}"


# ---- GTEx -------------------------------------------------------------------------------------------------------

def gtex_expression(gene: str, top: int = 12) -> str:
    """Median expression (TPM) of a human gene across GTEx tissues, highest first, with a tissue-specificity hint."""
    try:
        info = lit._json("https://gtexportal.org/api/v2/reference/gene", params={"geneId": gene, "gencodeVersion": "v26", "genomeBuild": "GRCh38/hg38"}).get("data", [])
        if not info:
            return f"GTEx found no gene {gene}"
        gid = info[0]["gencodeId"]
        rows = lit._json("https://gtexportal.org/api/v2/expression/medianGeneExpression", params={"gencodeId": gid, "datasetId": "gtex_v8", "itemsPerPage": 100}).get("data", [])
    except Exception as e:
        return _fail("GTEx ", e)
    rows = sorted(rows, key=lambda r: -r["median"])
    if not rows:
        return f"GTEx has no expression data for {gene} ({gid})."
    total = sum(r["median"] for r in rows) or 1
    share = rows[0]["median"] / total
    hint = f"the highest tissue accounts for {share:.0%} of the sum of tissue medians" + (", expression is highly concentrated, strongly tissue-specific" if share > 0.4 else ", broadly distributed")
    return f"GTEx v8: {info[0]['geneSymbol']} ({gid}) median TPM by tissue, top {top}; {hint}:\n" + "\n".join(f"{r['tissueSiteDetailId']} | {r['median']:.2f}" for r in rows[:top])


# ---- gnomAD -----------------------------------------------------------------------------------------------------

def gnomad_constraint(gene: str) -> str:
    """gnomAD v4 loss-of-function constraint: pLI, LOEUF (oe_lof_upper) and missense z. LOEUF < 0.35 means strongly constrained."""
    try:
        d = _post("https://gnomad.broadinstitute.org/api", {"query": 'query($g:String!){gene(gene_symbol:$g, reference_genome:GRCh38){symbol gnomad_constraint{pli oe_lof oe_lof_upper mis_z lof_z exp_lof obs_lof}}}',
                                                           "variables": {"g": gene}})["data"]["gene"]
    except Exception as e:
        return _fail("gnomAD ", e)
    if not d or not d.get("gnomad_constraint"):
        return f"gnomAD has no constraint data for {gene}"
    c = d["gnomad_constraint"]
    verdict = "strong constraint (loss-of-function variants are barely tolerated; inhibiting this target calls for safety caution)" if c["oe_lof_upper"] < 0.35 else ("moderate constraint" if c["oe_lof_upper"] < 0.6 else "weak constraint (loss-of-function variants are common in the population; inhibition is more likely to be tolerated)")
    return (f"gnomAD: {d['symbol']} pLI={c['pli']:.3f}, LOEUF={c['oe_lof_upper']:.3f} (expected LoF {c['exp_lof']:.1f}, observed {c['obs_lof']}), "
            f"missense z={c['mis_z']:.2f}, LoF z={c['lof_z']:.2f}. Reading: {verdict}.")


# ---- GEO --------------------------------------------------------------------------------------------------------

def geo_search(query: str, max_results: int = 10, entry_type: str = "gse") -> str:
    """Search GEO DataSets (NCBI gds): accession | title | organism | samples | type | date."""
    try:
        ids = lit._json(lit.EUTILS + "esearch.fcgi", params={"db": "gds", "term": f"({query}) AND {entry_type}[Entry Type]", "retmax": max_results, "retmode": "json", "sort": "relevance"})["esearchresult"]
        found = ((ids or {}).get("esearchresult") or ids or {}).get("idlist") or []
        if not found:
            err = ((ids or {}).get("esearchresult") or {}).get("ERROR")
            return f"GEO found nothing: {query}" + (f" (NCBI returned: {err})" if err else "")
        ids = {"idlist": found}
        summ = lit._json(lit.EUTILS + "esummary.fcgi", params={"db": "gds", "id": ",".join(ids["idlist"]), "retmode": "json"})["result"]
    except Exception as e:
        return _fail("GEO ", e)
    rows = []
    for uid in ids["idlist"]:
        s = summ.get(uid, {})
        rows.append(f"{s.get('accession')} | {(s.get('title') or '')[:100]} | {s.get('taxon')} | {s.get('n_samples')} samples | {s.get('gdstype')} | {s.get('pdat')}")
    return f"GEO: {ids['count']} records in all, first {len(rows)} ({query}):\n" + "\n".join(rows)


# ---- STRING / Reactome ------------------------------------------------------------------------------------------

def string_interactions(gene: str, limit: int = 15, species: int = 9606) -> str:
    """STRING protein interaction partners with combined confidence score (0-1)."""
    try:
        data = lit._json("https://string-db.org/api/json/interaction_partners", params={"identifiers": gene, "species": species, "limit": limit})
    except Exception as e:
        return _fail("STRING ", e)
    rows = [f"{d['preferredName_B']} | {d['score']:.3f}" for d in data]
    return f"STRING: interacting proteins of {gene} (combined score ≥ default threshold), first {len(rows)}:\n" + "\n".join(rows) if rows else f"STRING found no interactions for {gene}"


def reactome_pathways(gene_or_term: str, max_results: int = 10) -> str:
    """Reactome pathways that contain a gene/protein, or match a term: stable id | name."""
    try:
        data = lit._json("https://reactome.org/ContentService/search/query", params={"query": gene_or_term, "species": "Homo sapiens", "types": "Pathway", "cluster": "true", "pageSize": max_results})
    except Exception as e:
        return _fail("Reactome ", e)
    rows = []
    for grp in data.get("results", []):
        for e in grp.get("entries", []):
            rows.append(f"{e['stId']} | {re.sub('<[^>]+>', '', e['name'])}")
    return "\n".join(rows[:max_results]) or f"Reactome found nothing: {gene_or_term}"


# ---- Ensembl, PDB, AlphaFold DB, PubChem, OpenAlex (added in version 2026.11.06) -------------------------------

def ensembl_gene(gene: str) -> str:
    """Human gene in Ensembl (GRCh38): Ensembl ID, symbol, biotype, position, canonical transcript and description."""
    try:
        d = lit._json(f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene.strip()}", params={"content-type": "application/json"})
    except Exception as e:
        return _fail("Ensembl ", e)
    strand = "+" if d.get("strand") == 1 else "-"
    return (f"{d.get('id')} | {d.get('display_name')} | {d.get('biotype')} | chr{d.get('seq_region_name')}:{d.get('start')}-{d.get('end')} ({strand}) "
            f"| canonical {d.get('canonical_transcript')} | {d.get('description', '')}")


_UNIPROT_ACCESSION = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$")


def pdb_structures(query: str, max_results: int = 5) -> str:
    """Experimental PDB structures of a human gene (symbol, e.g. TP53) or of one UniProt accession (e.g. P04637), not a loose text match:
    PDB ID | title | method | resolution (A), with the total count."""
    q = query.strip()
    text = lambda attr, value: {"type": "terminal", "service": "text", "parameters": {"attribute": attr, "operator": "exact_match", "value": value}}
    if _UNIPROT_ACCESSION.match(q.upper()):
        node = text("rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession", q.upper())
        label = f"UniProt {q.upper()}"
    else:
        node = {"type": "group", "logical_operator": "and", "nodes": [
            text("rcsb_entity_source_organism.rcsb_gene_name.value", q),
            text("rcsb_entity_source_organism.ncbi_scientific_name", "Homo sapiens")]}
        label = f"{q} (human)"
    body = {"query": node, "return_type": "entry", "request_options": {"paginate": {"start": 0, "rows": max_results}}}
    try:
        data = _post("https://search.rcsb.org/rcsbsearch/v2/query", body)
    except Exception as e:
        if "404" in str(e) or "JSONDecode" in type(e).__name__ or "Expecting value" in str(e):  # an empty reply means no match
            return f"PDB found no structure for {label}"
        return _fail("PDB ", e)
    rows = []
    for hit in data.get("result_set", [])[:max_results]:
        pid = hit.get("identifier")
        try:
            e = lit._json(f"https://data.rcsb.org/rest/v1/core/entry/{pid}")
        except Exception:
            rows.append(f"{pid} | (details unavailable)")
            continue
        title = (e.get("struct") or {}).get("title", "")
        method = ((e.get("exptl") or [{}])[0]).get("method", "")
        res = ((e.get("rcsb_entry_info") or {}).get("resolution_combined") or [None])[0]
        rows.append(f"{pid} | {title} | {method} | {res if res is not None else 'n/a'}")
    if not rows:
        return f"PDB found no structure for {label}"
    return f"{data.get('total_count', len(rows))} PDB entries for {label}; the first {len(rows)}:\n" + "\n".join(rows)


def alphafold_structure(uniprot: str) -> str:
    """AlphaFold DB prediction for one UniProt accession: model ID, mean pLDDT (confidence, 0-100), created date and the structure file."""
    try:
        data = lit._json(f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot.strip()}")
    except Exception as e:
        if "404" in str(e):
            return f"AlphaFold DB has no prediction for {uniprot}"
        return _fail("AlphaFold ", e)
    if not data:
        return f"AlphaFold DB has no prediction for {uniprot}"
    row = data[0]
    return (f"{row.get('modelEntityId')} | mean pLDDT {row.get('globalMetricValue')} | created {str(row.get('modelCreatedDate', ''))[:10]} "
            f"| {row.get('pdbUrl')}")


def pubchem_compound(name: str) -> str:
    """PubChem compound by English name: CID | molecular formula | molecular weight | IUPAC name | SMILES."""
    from urllib.parse import quote

    url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name.strip())}"
           "/property/MolecularFormula,MolecularWeight,IUPACName,ConnectivitySMILES/JSON")
    try:
        props = lit._json(url)["PropertyTable"]["Properties"]
    except Exception as e:
        if "404" in str(e):
            return f"PubChem found no compound named: {name}"
        return _fail("PubChem ", e)
    rows = [f"{p.get('CID')} | {p.get('MolecularFormula')} | {p.get('MolecularWeight')} | {p.get('IUPACName', '')} | {p.get('ConnectivitySMILES', '')}"
            for p in props[:3]]
    return "\n".join(rows) or f"PubChem found no compound named: {name}"


def dgidb_interactions(gene: str, max_results: int = 15) -> str:
    """Drugs that target a gene (DGIdb): drug | approved | interaction type | score (higher = better supported) | sources. Human gene symbols."""
    query = {"query": '{ genes(names: ["%s"]) { nodes { name interactions { drug { name approved } interactionTypes { type } '
                      'interactionScore sources { sourceDbName } } } } }' % gene.strip().replace('"', "")}
    try:
        data = _post("https://dgidb.org/api/graphql", query)
    except Exception as e:
        return _fail("DGIdb ", e)
    nodes = ((data.get("data") or {}).get("genes") or {}).get("nodes") or []
    rows = []
    for n in nodes:
        for it in sorted(n.get("interactions") or [], key=lambda x: -(x.get("interactionScore") or 0))[:max_results]:
            drug = (it.get("drug") or {}).get("name", "")
            approved = "approved" if (it.get("drug") or {}).get("approved") else "investigational"
            types = ", ".join(t.get("type", "") for t in it.get("interactionTypes") or []) or "type not given"
            src = ", ".join(sorted({s.get("sourceDbName", "") for s in it.get("sources") or []}))
            rows.append(f"{drug} | {approved} | {types} | {it.get('interactionScore', 0):.3f} | {src}")
    if not rows:
        return f"DGIdb found no drug interaction for {gene}"
    return f"{len(rows)} drug interactions for {gene} (DGIdb), best supported first:\n" + "\n".join(rows[:max_results])


def openalex_works(query: str, max_results: int = 8) -> str:
    """OpenAlex scholarly works (broad coverage beyond PubMed, including preprints): year | title | DOI | venue."""
    import os

    params: dict[str, Any] = {"search": query, "per-page": max(1, min(int(max_results), 25)),
                              "select": "display_name,publication_year,doi,primary_location"}
    key = os.environ.get("BIOMNI_OPENALEX_KEY", "").strip()  # optional: a personal key has its own daily budget
    if key:
        params["api_key"] = key
    try:
        data = lit._json("https://api.openalex.org/works", params=params)
    except Exception as e:
        return _fail("OpenAlex ", e)
    rows = []
    for w in data.get("results", []):
        venue = (((w.get("primary_location") or {}).get("source")) or {}).get("display_name", "")
        rows.append(f"{w.get('publication_year')} | {w.get('display_name', '')} | {w.get('doi') or 'no DOI'} | {venue}")
    return "\n".join(rows) or f"OpenAlex found no works for: {query}"


# ---- a short cache for the database tools: the same gene or accession is often looked up again in the same work ----------------
# Only successful answers are kept (a failure is tried again next time), for 30 minutes, at most 500 entries. The connector switch
# (guard below) still runs on every call, so a switched-off database is never answered from the cache.
import functools as _functools
import time as _time

CACHE_SECONDS = 1800
CACHE_MAX = 500
_cache_store: dict[tuple, tuple[float, str]] = {}


def _cached(fn):
    @_functools.wraps(fn)
    def inner(*args, **kw):
        key = (fn.__name__, args, tuple(sorted(kw.items())))
        hit = _cache_store.get(key)
        if hit and _time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        out = fn(*args, **kw)
        if isinstance(out, str) and " failed:" not in out[:200] and "not found" not in out[:200].lower():
            if len(_cache_store) >= CACHE_MAX:
                _cache_store.pop(next(iter(_cache_store)))
            _cache_store[key] = (_time.time(), out)
        return out
    return inner


_CACHED_TOOLS = ("clinical_trials", "fda_adverse_events", "chembl_target_compounds", "open_targets", "target_tractability", "uniprot_lookup",
                 "gtex_expression", "gnomad_constraint", "geo_search", "string_interactions", "reactome_pathways", "ensembl_gene",
                 "pdb_structures", "alphafold_structure", "pubchem_compound", "openalex_works", "dgidb_interactions")
for _name in _CACHED_TOOLS:
    globals()[_name] = _cached(globals()[_name])


def clear_cache() -> int:
    """Forget every cached answer (for tests and for a user who wants fresh data now). Returns how many were kept."""
    n = len(_cache_store)
    _cache_store.clear()
    return n


from biomni_ui import connectors as _connectors  # noqa: E402
_connectors.guard(globals())  # the switch of each database connector is checked on every call
