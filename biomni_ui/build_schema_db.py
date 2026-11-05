"""Rebuild the API description files that the stock `query_*` database tools read (biomni/tool/schema_db/*.pkl).

The upstream package ships the tools but not these files, so `query_uniprot(prompt="...")` and 26 siblings fail before
they reach the network. Each file is a JSON-able dict that is pasted into the tool's system prompt; the model uses it to
turn a natural-language question into a request URL. Run `python -m biomni_ui.build_schema_db` to regenerate them.

Sources: machine-readable OpenAPI documents where the database publishes one (Reactome, cBioPortal, Monarch), otherwise a
hand-written description limited to endpoints that were called successfully while this file was written.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Any

import requests

OUT = Path(__file__).resolve().parent.parent / "biomni" / "tool" / "schema_db"
UA = {"User-Agent": "biomni-lite/0.1 (schema builder)", "Accept": "application/json"}


def ep(path: str, desc: str, params: dict[str, str] | None = None, example: str = "", method: str = "GET") -> dict[str, Any]:
    out: dict[str, Any] = {"path": path, "method": method, "description": desc}
    if params:
        out["parameters"] = params
    if example:
        out["example"] = example
    return out


def openapi_to_schema(url: str, base_url: str, description: str, notes: list[str], max_paths: int = 90) -> dict[str, Any]:
    """Shrink an OpenAPI document to path + summary + parameter names, which is all the model needs to build a URL."""
    spec = requests.get(url, headers=UA, timeout=60).json()
    endpoints = []
    for path, item in list(spec.get("paths", {}).items())[:max_paths]:
        for method, op in item.items():
            if method.lower() not in ("get", "post"):
                continue
            params = {}
            for p in op.get("parameters", []):
                params[p.get("name", "?")] = (f"({p.get('in', '')}{', required' if p.get('required') else ''}) " + (p.get("description") or "")[:70]).strip()
            endpoints.append(ep(path, (op.get("summary") or op.get("description") or "")[:140], params, method=method.upper()))
    return {"description": description, "base_url": base_url, "notes": notes, "endpoints": endpoints}


EUTILS_NOTES = ["Base https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ ; always add retmode=json where supported.", "Search with esearch.fcgi (returns ids), then esummary.fcgi?id=<ids> for records.",
                "At most about 3 requests per second."]

HAND: dict[str, dict[str, Any]] = {
    "uniprot": {
        "description": "UniProt protein knowledgebase REST API.", "base_url": "https://rest.uniprot.org",
        "notes": ["Human reviewed (Swiss-Prot) entries: add 'AND reviewed:true AND organism_id:9606' to the query.", "Exact gene symbol: gene_exact:TP53. Accession: accession:P04637.",
                  "format can be json, tsv, fasta, txt; fields is a comma list such as accession,gene_names,protein_name,length,cc_function,go_id,xref_pdb,sequence."],
        "endpoints": [
            ep("/uniprotkb/search", "Search entries.", {"query": "UniProt query syntax", "format": "json|tsv|fasta", "fields": "comma list of return fields", "size": "max 500"},
               "https://rest.uniprot.org/uniprotkb/search?query=gene_exact:TP53+AND+organism_id:9606+AND+reviewed:true&format=json&fields=accession,gene_names,protein_name,length&size=3"),
            ep("/uniprotkb/{accession}.json", "One entry by accession.", example="https://rest.uniprot.org/uniprotkb/P04637.json"),
            ep("/uniprotkb/{accession}.fasta", "Sequence as FASTA.", example="https://rest.uniprot.org/uniprotkb/P04637.fasta"),
            ep("/uniref/search", "UniRef clusters.", {"query": "e.g. uniprot_id:P04637 AND identity:0.9"}),
            ep("/proteomes/search", "Reference proteomes.", {"query": "e.g. organism_id:9606"}),
            ep("/taxonomy/search", "Taxonomy.", {"query": "scientific name or id"}),
        ],
    },
    "interpro": {
        "description": "InterPro protein families, domains and sites (EMBL-EBI).", "base_url": "https://www.ebi.ac.uk/interpro/api",
        "notes": ["URL pattern: /{main_data_type}/{main_db}[/{main_accession}][/{filter_type}/{filter_db}[/{filter_accession}]] ; add ?page_size=N.", "Types: entry, protein, structure, taxonomy, proteome, set. Databases: interpro, pfam, smart, prosite, cdd, uniprot, pdb."],
        "endpoints": [
            ep("/entry/interpro/protein/uniprot/{uniprot_accession}", "InterPro entries (domains/families) found in a protein.", example="https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot/P04637"),
            ep("/protein/uniprot/{uniprot_accession}", "Protein record with its length and sequence info.", example="https://www.ebi.ac.uk/interpro/api/protein/uniprot/P04637"),
            ep("/entry/interpro/{IPR_accession}", "Details of one InterPro entry.", example="https://www.ebi.ac.uk/interpro/api/entry/interpro/IPR011615"),
            ep("/entry/pfam/{PF_accession}", "A Pfam family.", example="https://www.ebi.ac.uk/interpro/api/entry/pfam/PF00870"),
            ep("/protein/uniprot/entry/interpro/{IPR_accession}", "Proteins that contain an InterPro entry.", {"page_size": "number of results"}),
            ep("/structure/pdb/protein/uniprot/{uniprot_accession}", "PDB structures of a protein."),
        ],
    },
    "pdb": {
        "description": "RCSB Protein Data Bank (Data API, Search API, FASTA).", "base_url": "https://data.rcsb.org/rest/v1",
        "notes": ["Entry ids are 4 characters, e.g. 1TUP.", "Full-text / attribute search uses https://search.rcsb.org/rcsbsearch/v2/query?json=<url-encoded JSON query> and returns identifiers; then fetch each with the Data API.",
                  "Search JSON: {\"query\":{\"type\":\"terminal\",\"service\":\"full_text\",\"parameters\":{\"value\":\"insulin\"}},\"return_type\":\"entry\",\"request_options\":{\"paginate\":{\"start\":0,\"rows\":10}}}"],
        "endpoints": [
            ep("/core/entry/{entry_id}", "Entry summary: title, method, resolution, authors, citation.", example="https://data.rcsb.org/rest/v1/core/entry/1TUP"),
            ep("/core/polymer_entity/{entry_id}/{entity_id}", "A polymer entity (chain group): sequence, source organism.", example="https://data.rcsb.org/rest/v1/core/polymer_entity/1TUP/1"),
            ep("/core/nonpolymer_entity/{entry_id}/{entity_id}", "A ligand entity."),
            ep("/core/uniprot/{entry_id}/{entity_id}", "UniProt mapping of an entity."),
            ep("https://www.rcsb.org/fasta/entry/{entry_id}", "Sequences of an entry as FASTA.", example="https://www.rcsb.org/fasta/entry/1TUP"),
            ep("https://search.rcsb.org/rcsbsearch/v2/query", "Search structures.", {"json": "URL-encoded search JSON (see notes)"}),
        ],
    },
    "kegg": {
        "description": "KEGG REST API (pathways, genes, compounds, drugs, diseases). Responses are plain text, tab-separated.", "base_url": "https://rest.kegg.jp",
        "notes": ["Organism codes: hsa human, mmu mouse. Gene entries look like hsa:7157 (NCBI gene id). Pathway ids like hsa05200 or map05200.", "Databases: pathway, brite, module, ko, genes, compound, drug, disease, organism."],
        "endpoints": [
            ep("/find/{database}/{query}", "Search entries by keyword.", example="https://rest.kegg.jp/find/genes/TP53+human"),
            ep("/list/{database}[/{organism}]", "List entries (e.g. all human pathways).", example="https://rest.kegg.jp/list/pathway/hsa"),
            ep("/get/{entry}[/{option}]", "One entry; option aaseq, ntseq, kgml, image, json.", example="https://rest.kegg.jp/get/hsa:7157"),
            ep("/link/{target_db}/{source}", "Cross-references, e.g. genes of a pathway or pathways of a gene.", example="https://rest.kegg.jp/link/pathway/hsa:7157"),
            ep("/conv/{target_db}/{source_db}", "Convert identifiers (ncbi-geneid, uniprot).", example="https://rest.kegg.jp/conv/uniprot/hsa:7157"),
            ep("/info/{database}", "Database release info."),
        ],
    },
    "stringdb": {
        "description": "STRING protein-protein interaction networks.", "base_url": "https://string-db.org/api",
        "notes": ["URL: /{format}/{method}?identifiers=...&species=9606 ; format json|tsv|tsv-no-header|image|svg.", "Several identifiers are separated by %0d (carriage return). required_score is 0-1000 (default 400; 700 high confidence).",
                  "Human 9606, mouse 10090."],
        "endpoints": [
            ep("/json/get_string_ids", "Map names to STRING ids.", {"identifiers": "names", "species": "taxon id"}),
            ep("/json/interaction_partners", "Interaction partners of proteins.", {"identifiers": "names", "species": "taxon id", "limit": "max partners", "required_score": "0-1000"},
               "https://string-db.org/api/json/interaction_partners?identifiers=TP53&species=9606&limit=10"),
            ep("/json/network", "Interactions among the input proteins (and optionally added neighbours).", {"identifiers": "names", "species": "taxon id", "add_nodes": "extra neighbours", "network_type": "functional|physical"}),
            ep("/json/enrichment", "GO/KEGG/Reactome/Pfam enrichment of a protein set.", {"identifiers": "names", "species": "taxon id"}),
            ep("/json/functional_annotation", "Annotations of input proteins.", {"identifiers": "names", "species": "taxon id"}),
            ep("/json/ppi_enrichment", "Is the set more connected than random?", {"identifiers": "names", "species": "taxon id"}),
            ep("/json/homology", "Homologous proteins.", {"identifiers": "names", "species": "taxon id"}),
        ],
    },
    "clinvar": {
        "description": "ClinVar (variant clinical significance) through NCBI E-utilities, db=clinvar.", "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        "notes": EUTILS_NOTES + ["Query fields: BRCA1[gene], pathogenic[clinsig], \"likely pathogenic\"[clinsig], single nucleotide variant[type of variation], 17[chr], rs80357906[rsid], \"breast cancer\"[disease/phenotype]."],
        "endpoints": [
            ep("/esearch.fcgi", "Find ClinVar variation ids.", {"db": "clinvar", "term": "e.g. BRCA1[gene] AND pathogenic[clinsig]", "retmax": "number", "retmode": "json"},
               "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term=BRCA1[gene]+AND+pathogenic[clinsig]&retmax=5&retmode=json"),
            ep("/esummary.fcgi", "Summaries (title, clinical significance, genes, conditions).", {"db": "clinvar", "id": "comma-separated ids", "retmode": "json"}),
            ep("/efetch.fcgi", "Full records.", {"db": "clinvar", "id": "ids", "rettype": "vcv", "retmode": "xml"}),
        ],
    },
    "geo": {
        "description": "NCBI GEO datasets and series through E-utilities, db=gds.", "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        "notes": EUTILS_NOTES + ["Entry types: gse (series), gsm (sample), gds (curated dataset), gpl (platform). Example term: (CAR-T[All Fields]) AND gse[Entry Type] AND \"Homo sapiens\"[Organism].",
                                 "A GSE's own page: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345&targ=self&form=text&view=brief"],
        "endpoints": [
            ep("/esearch.fcgi", "Find GEO records.", {"db": "gds", "term": "query with [Entry Type], [Organism], [All Fields]", "retmax": "n", "retmode": "json"},
               "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gds&term=(CAR-T[All Fields])+AND+gse[Entry Type]&retmax=5&retmode=json"),
            ep("/esummary.fcgi", "Title, accession, organism, sample count, type.", {"db": "gds", "id": "ids from esearch", "retmode": "json"}),
        ],
    },
    "dbsnp": {
        "description": "dbSNP variants: NCBI Variation Services and E-utilities.", "base_url": "https://api.ncbi.nlm.nih.gov/variation/v0",
        "notes": ["rs numbers are given without the 'rs' prefix in the Variation API path.", "Genomic coordinates are GRCh38 unless stated."],
        "endpoints": [
            ep("/refsnp/{rs_number_without_rs}", "Full refSNP record: alleles, placement on genes, clinical annotations, frequencies.", example="https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/334"),
            ep("/refsnp/{rs_number}/frequency", "Allele frequencies per study (gnomAD, 1000 Genomes...)."),
            ep("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", "Search dbSNP.", {"db": "snp", "term": "e.g. TP53[Gene Name] AND missense variant[Function Class]", "retmode": "json"}),
        ],
    },
    "ensembl": {
        "description": "Ensembl REST API (genes, transcripts, sequences, variants, homology, VEP).", "base_url": "https://rest.ensembl.org",
        "notes": ["Always append ?content-type=application/json (or send the header).", "Human species name: homo_sapiens. Gene ids ENSG..., transcripts ENST..., proteins ENSP....", "Regions look like 17:7661779-7687550:1 (chr:start-end:strand), GRCh38."],
        "endpoints": [
            ep("/lookup/symbol/{species}/{symbol}", "Gene by symbol.", {"expand": "1 to include transcripts"}, "https://rest.ensembl.org/lookup/symbol/homo_sapiens/TP53?content-type=application/json"),
            ep("/lookup/id/{ensembl_id}", "Any object by Ensembl id.", {"expand": "1"}),
            ep("/sequence/id/{ensembl_id}", "Sequence.", {"type": "genomic|cds|cdna|protein"}),
            ep("/sequence/region/{species}/{region}", "Genomic sequence of a region."),
            ep("/overlap/region/{species}/{region}", "Features (gene, transcript, variation, regulatory) overlapping a region.", {"feature": "gene|transcript|variation|regulatory"}),
            ep("/xrefs/symbol/{species}/{symbol}", "Cross-references of a symbol."),
            ep("/vep/{species}/hgvs/{hgvs_notation}", "Variant effect prediction from HGVS.", example="https://rest.ensembl.org/vep/human/hgvs/ENST00000269305.9:c.817C>T?content-type=application/json"),
            ep("/vep/{species}/region/{region}/{allele}", "VEP from a position, e.g. 17:7675088-7675088:1/T."),
            ep("/homology/id/{species}/{ensembl_gene_id}", "Orthologues and paralogues.", {"type": "orthologues|paralogues", "target_species": "species"}),
            ep("/info/species", "Available species."),
        ],
    },
    "opentarget": {
        "description": "Open Targets Platform GraphQL API (target-disease evidence, tractability, drugs).", "base_url": "https://api.platform.opentargets.org/api/v4/graphql",
        "notes": ["POST a JSON body {\"query\": \"...\", \"variables\": {...}}. Ids: target = Ensembl gene id (ENSG...), disease = EFO/MONDO id, drug = ChEMBL id.", "First resolve a name to an id with the search query.",
                  "Use only fields listed in the examples; unknown fields make the request fail with HTTP 400."],
        "queries": {
            "search": 'query($q:String!){search(queryString:$q,entityNames:["target","disease","drug"],page:{index:0,size:5}){hits{id name entity description}}}',
            "target_summary": 'query($id:String!){target(ensemblId:$id){id approvedSymbol approvedName biotype functionDescriptions tractability{label modality value} drugAndClinicalCandidates{count}}}',
            "target_diseases": 'query($id:String!,$n:Int!){target(ensemblId:$id){approvedSymbol associatedDiseases(page:{index:0,size:$n}){count rows{score disease{id name}}}}}',
            "disease_targets": 'query($id:String!,$n:Int!){disease(efoId:$id){name associatedTargets(page:{index:0,size:$n}){count rows{score target{id approvedSymbol approvedName}}}}}',
            "disease_info": 'query($id:String!){disease(efoId:$id){id name description synonyms{terms} therapeuticAreas{name}}}',
            "drug_info": 'query($id:String!){drug(chemblId:$id){id name drugType maximumClinicalTrialPhase mechanismsOfAction{rows{mechanismOfAction targets{approvedSymbol}}}}}',
        },
        "endpoints": [ep("", "Single GraphQL endpoint; choose one of the queries above and fill the variables.", {"query": "GraphQL text", "variables": "JSON"}, method="POST")],
    },
    "openfda": {
        "description": "openFDA: drug adverse events (FAERS), labels, recalls, NDC, device events.", "base_url": "https://api.fda.gov",
        "notes": ["URL: /{category}/{endpoint}.json?search=FIELD:term&limit=N ; combine with +AND+ ; quote phrases.", "count=FIELD.exact returns the most frequent values of a field (use it for 'top reactions').",
                  "FAERS reports are spontaneous and do not give incidence or causality.", "Drug name field: patient.drug.medicinalproduct (brand, as reported) or patient.drug.openfda.generic_name."],
        "endpoints": [
            ep("/drug/event.json", "Adverse event reports.", {"search": "e.g. patient.drug.medicinalproduct:\"PEMBROLIZUMAB\"", "count": "patient.reaction.reactionmeddrapt.exact", "limit": "n (max 1000)"},
               "https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:\"PEMBROLIZUMAB\"&count=patient.reaction.reactionmeddrapt.exact&limit=10"),
            ep("/drug/label.json", "Drug labels (indications, warnings, dosage).", {"search": "openfda.generic_name:\"metformin\"", "limit": "n"}),
            ep("/drug/enforcement.json", "Drug recalls.", {"search": "e.g. reason_for_recall:contamination", "limit": "n"}),
            ep("/drug/ndc.json", "National Drug Code directory.", {"search": "generic_name:\"insulin\""}),
            ep("/device/event.json", "Device adverse events.", {"search": "device.generic_name:pacemaker"}),
        ],
    },
    "gwas_catalog": {
        "description": "NHGRI-EBI GWAS Catalog REST API.", "base_url": "https://www.ebi.ac.uk/gwas/rest/api",
        "notes": ["HAL+JSON responses; add size=N and page=P.", "Trait names are free text; EFO trait ids look like EFO_0000305."],
        "endpoints": [
            ep("/efoTraits/search/findByEfoTrait", "Find a trait by name.", {"trait": "e.g. breast carcinoma"}),
            ep("/associations/search/findByRsId", "Associations of one SNP.", {"rsId": "rs number"}),
            ep("/singleNucleotidePolymorphisms/{rsId}", "SNP record.", example="https://www.ebi.ac.uk/gwas/rest/api/singleNucleotidePolymorphisms/rs7329174"),
            ep("/studies/{accession}", "A study by GCST accession."),
        ],
    },
    "gnomad": {
        "description": "gnomAD GraphQL API (population allele frequencies and gene constraint).", "base_url": "https://gnomad.broadinstitute.org/api",
        "notes": ["POST {\"query\": \"...\", \"variables\": {...}}. reference_genome is GRCh38; datasets gnomad_r4 (v4), gnomad_r2_1 (v2).", "Variant ids are chrom-pos-ref-alt, e.g. 17-7675088-C-T.", "Use only the fields shown in the examples."],
        "queries": {
            "gene_constraint": 'query($g:String!){gene(gene_symbol:$g,reference_genome:GRCh38){gene_id symbol chrom start stop gnomad_constraint{pli oe_lof oe_lof_upper mis_z lof_z exp_lof obs_lof}}}',
            "variant_frequency": 'query($v:String!){variant(variantId:$v,dataset:gnomad_r4){variant_id rsids exome{ac an af} genome{ac an af}}}',
        },
        "endpoints": [ep("", "Single GraphQL endpoint.", {"query": "GraphQL text", "variables": "JSON"}, method="POST")],
    },
    "pubchem": {
        "description": "PubChem PUG REST (compounds, substances, assays).", "base_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
        "notes": ["URL: /{domain}/{namespace}/{identifiers}/{operation}/{output}. domain compound|substance|assay; namespace cid|name|smiles|inchikey|formula.", "Properties: MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,IUPACName.",
                  "Output JSON|CSV|TXT|SDF|PNG. SMILES containing '/' or '#' must be URL-encoded.", "At most 5 requests per second."],
        "endpoints": [
            ep("/compound/name/{name}/property/{property_list}/JSON", "Properties by compound name.", example="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/MolecularFormula,MolecularWeight,CanonicalSMILES/JSON"),
            ep("/compound/cid/{cid}/property/{property_list}/JSON", "Properties by CID."),
            ep("/compound/name/{name}/cids/JSON", "CIDs for a name."),
            ep("/compound/name/{name}/synonyms/JSON", "Synonyms."),
            ep("/compound/smiles/{smiles}/cids/JSON", "CIDs for a structure."),
            ep("/compound/cid/{cid}/assaysummary/JSON", "Bioassay results of a compound."),
            ep("https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON", "Full annotated record (pharmacology, safety, literature)."),
        ],
    },
    "ucsc": {
        "description": "UCSC Genome Browser REST API.", "base_url": "https://api.genome.ucsc.edu",
        "notes": ["Parameters are separated with semicolons or &: ?genome=hg38;chrom=chr17;start=7661778;end=7687550 (start is 0-based).", "Assemblies: hg38, hg19, mm39, mm10."],
        "endpoints": [
            ep("/list/ucscGenomes", "All genome assemblies.", example="https://api.genome.ucsc.edu/list/ucscGenomes"),
            ep("/list/chromosomes", "Chromosomes of an assembly.", {"genome": "hg38"}),
            ep("/list/tracks", "Tracks available for an assembly.", {"genome": "hg38"}),
            ep("/getData/sequence", "DNA sequence of a region.", {"genome": "hg38", "chrom": "chr17", "start": "0-based", "end": "end"}),
            ep("/getData/track", "Track items in a region (e.g. knownGene, gnomadGenomesVariantsV3).", {"genome": "hg38", "track": "name", "chrom": "chr", "start": "n", "end": "n"}),
            ep("/search", "Find a gene or position by name.", {"search": "TP53", "genome": "hg38"}),
        ],
    },
    "jaspar": {
        "description": "JASPAR transcription-factor binding profiles.", "base_url": "https://jaspar.elixir.no/api/v1",
        "notes": ["Add format=json. Matrix ids look like MA0106.3 (base id + version).", "collection CORE is the curated set; tax_group vertebrates, plants, insects..."],
        "endpoints": [
            ep("/matrix/", "Search matrices.", {"search": "TF name", "collection": "CORE", "tax_group": "vertebrates", "tax_id": "9606", "page_size": "n", "format": "json"}, "https://jaspar.elixir.no/api/v1/matrix/?search=TP53&collection=CORE&format=json"),
            ep("/matrix/{matrix_id}/", "One profile with its frequency matrix.", {"format": "json"}),
            ep("/species/", "Species list."),
            ep("/taxon/", "Taxonomic groups."),
        ],
    },
    "pride": {
        "description": "PRIDE Archive proteomics projects (EMBL-EBI).", "base_url": "https://www.ebi.ac.uk/pride/ws/archive/v2",
        "notes": ["Pagination: pageSize and page (0-based).", "Project accessions look like PXD000001."],
        "endpoints": [
            ep("/projects", "Search projects.", {"keyword": "free text", "pageSize": "n", "page": "0", "sortDirection": "DESC", "sortConditions": "submissionDate"}, "https://www.ebi.ac.uk/pride/ws/archive/v2/projects?keyword=glioblastoma&pageSize=5&page=0"),
            ep("/projects/{accession}", "One project.", example="https://www.ebi.ac.uk/pride/ws/archive/v2/projects/PXD000001"),
            ep("/files/byProject", "Files of a project.", {"accession": "PXD id"}),
        ],
    },
    "emdb": {
        "description": "Electron Microscopy Data Bank.", "base_url": "https://www.ebi.ac.uk/emdb/api",
        "notes": ["Entry ids look like EMD-1234."],
        "endpoints": [
            ep("/entry/{emdb_id}", "Entry metadata.", example="https://www.ebi.ac.uk/emdb/api/entry/EMD-1234"),
            ep("/search/{query}", "Search.", {"rows": "n", "fl": "fields to return"}, "https://www.ebi.ac.uk/emdb/api/search/ribosome?rows=5&fl=emdb_id,title"),
        ],
    },
    "gtopdb": {
        "description": "IUPHAR/BPS Guide to PHARMACOLOGY.", "base_url": "https://www.guidetopharmacology.org/services",
        "notes": ["Responses are JSON arrays."],
        "endpoints": [
            ep("/targets", "Search targets.", {"name": "target name", "geneSymbol": "gene", "type": "GPCR|Enzyme|..."}, "https://www.guidetopharmacology.org/services/targets?geneSymbol=EGFR"),
            ep("/ligands", "Search ligands.", {"name": "ligand name", "type": "Synthetic organic|Antibody|..."}),
            ep("/targets/{targetId}/interactions", "Ligands acting on a target with affinities."),
            ep("/ligands/{ligandId}/interactions", "Targets of a ligand."),
        ],
    },
    "remap": {
        "description": "ReMap regulatory regions (transcription-factor ChIP-seq peaks). The public API was unreachable (HTTP 502) when this description was written, so treat it as unverified.",
        "base_url": "https://remap.univ-amu.fr/api/v1", "notes": ["Fall back to downloads at https://remap.univ-amu.fr/download_page when the API is down."],
        "endpoints": [ep("/catalogue/tf", "Peaks of a transcription factor.", {"tf": "TF name", "species": "human"})],
    },
    "mpd": {
        "description": "Mouse Phenome Database. The API returned HTTP 404 on its documented root when this description was written, so treat it as unverified.",
        "base_url": "https://phenomedoc.jax.org/MPD_API", "notes": ["If requests fail, use the web interface https://phenome.jax.org."],
        "endpoints": [ep("/strains", "Mouse strains.")],
    },
    "iucn": {
        "description": "IUCN Red List API v4. Needs a personal API token (header 'Authorization: <token>'), which this installation does not have.",
        "base_url": "https://api.iucnredlist.org/api/v4", "notes": ["Say clearly that a token is required instead of guessing results."],
        "endpoints": [ep("/taxa/scientific_name", "Assessment by scientific name.", {"genus_name": "Genus", "species_name": "species"})],
    },
    "pbdb": {
        "description": "Paleobiology Database data service 1.2.", "base_url": "https://paleobiodb.org/data1.2",
        "notes": ["Add .json to the operation path. Common params: base_name, taxon_name, show (e.g. class,coords,loc), limit."],
        "endpoints": [
            ep("/taxa/list.json", "Taxa below/matching a name.", {"base_name": "e.g. Dinosauria", "rank": "genus", "show": "attr,app", "limit": "n"}, "https://paleobiodb.org/data1.2/taxa/list.json?base_name=Dinosauria&rank=genus&limit=5"),
            ep("/taxa/single.json", "One taxon.", {"name": "taxon name"}),
            ep("/occs/list.json", "Fossil occurrences.", {"base_name": "taxon", "interval": "e.g. Cretaceous", "show": "coords,loc", "limit": "n"}),
        ],
    },
    "worms": {
        "description": "World Register of Marine Species (WoRMS) REST service.", "base_url": "https://www.marinespecies.org/rest",
        "notes": ["Responses are JSON; AphiaID is the stable species id. A 204 status means no match."],
        "endpoints": [
            ep("/AphiaRecordsByName/{scientific_name}", "Records matching a name.", {"like": "true for prefix match", "marine_only": "true|false"}, "https://www.marinespecies.org/rest/AphiaRecordsByName/Solea%20solea?like=false&marine_only=true"),
            ep("/AphiaRecordByAphiaID/{aphia_id}", "One record."),
            ep("/AphiaClassificationByAphiaID/{aphia_id}", "Full classification."),
            ep("/AphiaChildrenByAphiaID/{aphia_id}", "Children taxa."),
            ep("/AphiaVernacularsByAphiaID/{aphia_id}", "Common names."),
        ],
    },
}

HAND.update({
    "chembl": {
        "description": "ChEMBL bioactivity database (EMBL-EBI) REST API.", "base_url": "https://www.ebi.ac.uk/chembl/api/data",
        "notes": ["Append .json to the resource name. Paging: limit and offset. Filters are Django-style: field__icontains, field__exact, field__lte, field__gte.",
                  "Ids: CHEMBLnnn for molecules, targets and assays. Human single-protein targets have target_type=SINGLE PROTEIN and organism=Homo sapiens.",
                  "Potency lives in /activity: standard_type (IC50, Ki, Kd, EC50), standard_value, standard_units (nM), standard_relation ('=')."],
        "endpoints": [
            ep("/molecule/search.json", "Free-text molecule search.", {"q": "name or synonym", "limit": "n"}, "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?q=imatinib&limit=3"),
            ep("/molecule/{chembl_id}.json", "One molecule: structures, max phase, ATC codes.", example="https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL941.json"),
            ep("/target/search.json", "Free-text target search.", {"q": "gene or protein name", "limit": "n"}),
            ep("/activity.json", "Measured activities.", {"target_chembl_id": "CHEMBL203", "molecule_chembl_id": "id", "standard_type": "IC50", "standard_units": "nM", "limit": "n", "order_by": "standard_value"}),
            ep("/mechanism.json", "Mechanism of action of a drug (empty for compounds that are not approved drugs).", {"molecule_chembl_id": "id"}),
            ep("/drug_indication.json", "Indications of a drug with trial phase.", {"molecule_chembl_id": "id"}, "https://www.ebi.ac.uk/chembl/api/data/drug_indication.json?molecule_chembl_id=CHEMBL941&limit=5"),
            ep("/assay.json", "Assays.", {"target_chembl_id": "id", "assay_type": "B|F|A"}),
        ],
    },
    "unichem": {
        "description": "UniChem: cross-references of one compound between chemistry databases.", "base_url": "https://www.ebi.ac.uk/unichem/api/v1",
        "notes": ["Use POST /compounds with a JSON body; type is one of inchikey, inchi, sourceID, uci. GET /sources lists the databases with their numeric ids."],
        "endpoints": [
            ep("/compounds", "Find a compound and its identifiers in all sources.", {"type": "inchikey", "compound": "e.g. RZVAJINKPMORJF-UHFFFAOYSA-N", "sourceID": "needed when type=sourceID"}, method="POST"),
            ep("/sources", "All source databases and their ids.", example="https://www.ebi.ac.uk/unichem/api/v1/sources"),
        ],
    },
    "clinicaltrials": {
        "description": "ClinicalTrials.gov API v2 (registered studies).", "base_url": "https://clinicaltrials.gov/api/v2",
        "notes": ["Query parameters: query.cond (condition), query.intr (intervention), query.term (anything), query.spons (sponsor), query.locn, filter.overallStatus (RECRUITING, COMPLETED, ...), pageSize, countTotal=true, format=json.",
                  "fields=NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName,StartDate limits what is returned.", "Phases: EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4."],
        "endpoints": [
            ep("/studies", "Search studies.", {"query.cond": "condition", "query.intr": "intervention", "query.term": "free text", "query.spons": "sponsor", "filter.overallStatus": "status", "pageSize": "n", "countTotal": "true"},
               "https://clinicaltrials.gov/api/v2/studies?query.cond=beta+thalassemia&query.intr=gene+therapy&pageSize=5&countTotal=true&format=json"),
            ep("/studies/{NCT_id}", "One study in full.", {"format": "json", "fields": "optional field list"}, "https://clinicaltrials.gov/api/v2/studies/NCT04211480?format=json"),
            ep("/stats/size", "Registry size statistics."),
        ],
    },
    "dailymed": {
        "description": "DailyMed (NLM) drug labels (SPL).", "base_url": "https://dailymed.nlm.nih.gov/dailymed/services/v2",
        "notes": ["Add .json. pagesize and page for paging. A set id (setid) identifies one label."],
        "endpoints": [
            ep("/spls.json", "Search labels.", {"drug_name": "name", "pagesize": "n"}, "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name=metformin&pagesize=5"),
            ep("/spls/{setid}.json", "One label (JSON summary); /spls/{setid}.xml has the full text."),
            ep("/drugnames.json", "Drug names (B = brand, G = generic).", {"drug_name": "prefix", "pagesize": "n"}),
            ep("/drugclasses.json", "Drug classes."),
            ep("/spls/{setid}/ndcs.json", "NDC codes of a label."),
        ],
    },
    "quickgo": {
        "description": "QuickGO: Gene Ontology terms and annotations (EMBL-EBI).", "base_url": "https://www.ebi.ac.uk/QuickGO/services",
        "notes": ["GO ids look like GO:0006915. Gene products are written UniProtKB:P04637.", "Responses: {numberOfHits, results:[...]}; limit and page for paging."],
        "endpoints": [
            ep("/ontology/go/terms/{go_ids}", "Term details (name, definition, aspect); ids comma-separated.", example="https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/GO:0006915"),
            ep("/ontology/go/search", "Find terms by words.", {"query": "e.g. apoptosis", "limit": "n"}),
            ep("/ontology/go/terms/{go_id}/children", "Child terms."),
            ep("/annotation/search", "Annotations.", {"geneProductId": "UniProtKB:P04637", "goId": "GO:0006915", "taxonId": "9606", "aspect": "biological_process|molecular_function|cellular_component", "limit": "n"},
               "https://www.ebi.ac.uk/QuickGO/services/annotation/search?geneProductId=UniProtKB:P04637&limit=10"),
        ],
    },
    "encode": {
        "description": "ENCODE Project portal (experiments, files, biosamples).", "base_url": "https://www.encodeproject.org",
        "notes": ["Search: /search/?type=Experiment&...&format=json&limit=N. Useful filters: assay_title (e.g. TF ChIP-seq, ATAC-seq, RNA-seq), target.label (e.g. CTCF), biosample_ontology.term_name (e.g. K562), status=released, organism.scientific_name=Homo sapiens.",
                  "An empty result is returned with HTTP 404 and an empty @graph: loosen the filters instead of treating it as an error.", "assay_title must be the exact ENCODE term: 'TF ChIP-seq', 'Histone ChIP-seq', 'ATAC-seq', 'DNase-seq', 'RNA-seq', 'eCLIP'. assay_title=ChIP-seq matches nothing.", "Experiment accessions look like ENCSR000AKO; files ENCFF000ABC."],
        "endpoints": [
            ep("/search/", "Search any object type.", {"type": "Experiment|File|Biosample|Annotation", "assay_title": "assay", "target.label": "factor", "biosample_ontology.term_name": "cell type", "status": "released", "format": "json", "limit": "n"},
               "https://www.encodeproject.org/search/?type=Experiment&assay_title=TF+ChIP-seq&target.label=CTCF&status=released&format=json&limit=5"),
            ep("/experiments/{accession}/", "One experiment with its files.", {"format": "json"}),
            ep("/files/{accession}/", "One file (download link in href).", {"format": "json"}),
        ],
    },
})

HAND["pdb"] = {
    "description": "RCSB PDB Search API v2 (https://search.rcsb.org/rcsbsearch/v2/query). The reply is a JSON query object; identifiers found are then fetched from the Data API.",
    "search_services": {
        "full_text": {"use": "keywords across all fields", "parameters": {"value": "search words"}},
        "text": {"use": "one attribute compared with a value", "parameters": {"attribute": "see common_attributes", "operator": "see operators", "value": "string, number or list"}},
        "text_chem": {"use": "chemical component attributes", "parameters": {"attribute": "e.g. chem_comp.name", "operator": "contains_words", "value": "string"}},
        "sequence": {"use": "sequence similarity (MMseqs2)", "parameters": {"target": "pdb_protein_sequence|pdb_dna_sequence|pdb_na_sequence", "value": "the sequence", "identity_cutoff": "0-1", "evalue_cutoff": "number"}},
        "seqmotif": {"use": "sequence motif", "parameters": {"value": "PROSITE or regex pattern", "pattern_type": "prosite|regex|simple", "target": "pdb_protein_sequence"}},
        "structure": {"use": "3D shape similarity", "parameters": {"value": {"entry_id": "4HHB", "assembly_id": "1"}, "operator": "strict_shape_match|relaxed_shape_match"}},
    },
    "operators": ["exact_match", "in", "contains_words", "contains_phrase", "equals", "greater", "greater_or_equal", "less", "less_or_equal", "range", "exists"],
    "common_attributes": {
        "struct.title": "entry title (contains_words)",
        "rcsb_polymer_entity.pdbx_description": "molecule name, e.g. 'Cellular tumor antigen p53' (contains_words)",
        "rcsb_entity_source_organism.ncbi_scientific_name": "source organism, e.g. 'Homo sapiens' (exact_match)",
        "exptl.method": "'X-RAY DIFFRACTION', 'ELECTRON MICROSCOPY', 'SOLUTION NMR' (exact_match)",
        "rcsb_entry_info.resolution_combined": "resolution in angstrom (less_or_equal, e.g. 2.5)",
        "rcsb_accession_info.initial_release_date": "ISO date (greater / range)",
        "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession": "UniProt accession, e.g. P04637 (exact_match)",
        "rcsb_entry_info.polymer_entity_count_DNA": "number of DNA entities (greater 0 = contains DNA)",
        "rcsb_entry_info.polymer_entity_count_protein": "number of protein entities",
        "rcsb_entry_info.deposited_atom_count": "atoms in the model",
        "struct_keywords.pdbx_keywords": "keywords such as 'TRANSCRIPTION'",
        "rcsb_primary_citation.pdbx_database_id_PubMed": "PubMed id of the primary paper",
        "entity_poly.rcsb_entity_polymer_type": "'Protein', 'DNA', 'RNA'",
    },
    "return_types": {"entry": "PDB entry ids (default)", "polymer_entity": "ids like 1TUP_1", "assembly": "ids like 1TUP-1", "non_polymer_entity": "ligand entities", "mol_definition": "chemical components"},
    "combine": "Group several conditions: {\"type\":\"group\",\"logical_operator\":\"and\",\"nodes\":[<terminal>,<terminal>]}. A terminal is {\"type\":\"terminal\",\"service\":\"text\",\"parameters\":{...}}.",
    "examples": [
        {"question": "insulin structures", "query": {"query": {"type": "terminal", "service": "full_text", "parameters": {"value": "insulin"}}, "return_type": "entry"}},
        {"question": "human p53 structures with DNA, resolution better than 3 A", "query": {"query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity.pdbx_description", "operator": "contains_words", "value": "p53"}},
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entity_source_organism.ncbi_scientific_name", "operator": "exact_match", "value": "Homo sapiens"}},
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entry_info.polymer_entity_count_DNA", "operator": "greater", "value": 0}},
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entry_info.resolution_combined", "operator": "less_or_equal", "value": 3.0}}]}, "return_type": "entry"}},
        {"question": "structures of UniProt P04637", "query": {"query": {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession", "operator": "exact_match", "value": "P04637"}}, "return_type": "entry"}},
    ],
}

OPENAPI = {
    "reactome": ("https://reactome.org/ContentService/v3/api-docs", "https://reactome.org/ContentService", "Reactome pathway knowledgebase (ContentService).",
                 ["Pathway ids look like R-HSA-109581. Species name 'Homo sapiens'.", "/search/query is the best first call for a gene or term."]),
    "cbioportal": ("https://www.cbioportal.org/api/v3/api-docs", "https://www.cbioportal.org/api", "cBioPortal cancer genomics.",
                   ["Typical flow: list studies, pick a studyId, then query molecular profiles / mutations / clinical data for that study.", "Studies look like brca_tcga; molecular profile ids look like brca_tcga_mutations."]),
    "monarch": ("https://api-v3.monarchinitiative.org/openapi.json", "https://api-v3.monarchinitiative.org/v3/api", "Monarch Initiative: genes, diseases, phenotypes and their associations.",
                ["Ids: MONDO diseases, HP phenotypes, HGNC/NCBIGene genes.", "Working patterns: /search?q=cystic%20fibrosis&category=biolink:Disease&limit=5 ; /entity/MONDO:0009061 ; /association?object=MONDO:0009061&limit=20 (genes, phenotypes and more linked to a disease) ; /association?subject=HGNC:1884&limit=20 (associations of a gene) ; add &category=biolink:CausalGeneToDiseaseAssociation to filter.", "Do NOT use /entity/{id}/{category} for these questions (HTTP 422)."]),
}


def build(out: Path = OUT, only: list[str] | None = None) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, str] = {}
    for name, schema in HAND.items():
        if only and name not in only:
            continue
        (out / f"{name}.pkl").write_bytes(pickle.dumps(schema))
        report[name] = f"hand-written, {len(schema.get('endpoints') or schema.get('search_services') or [])} entries"
    for name, (url, base, desc, notes) in OPENAPI.items():
        if only and name not in only:
            continue
        try:
            schema = openapi_to_schema(url, base, desc, notes)
            (out / f"{name}.pkl").write_bytes(pickle.dumps(schema))
            report[name] = f"from OpenAPI, {len(schema['endpoints'])} endpoints"
        except Exception as e:  # keep going: one unreachable spec must not block the other files
            report[name] = f"FAILED {type(e).__name__}: {str(e)[:80]}"
    return report


if __name__ == "__main__":
    for k, v in build(only=sys.argv[1:] or None).items():
        print(f"{k:14} {v}")
