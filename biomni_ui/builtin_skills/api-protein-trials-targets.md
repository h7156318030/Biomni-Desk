---
title: Recipes for protein, clinical trial and target APIs (UniProt, ClinicalTrials.gov, Open Targets)
description: Correct ways to call the UniProt REST API, the ClinicalTrials.gov v2 API and the Open Targets GraphQL API with curl, and the common errors
category: Data & workflows
when_to_use: You need a protein's sequence length, function or chromosome; the trial registrations for a drug or disease (phase, status); the diseases most strongly associated with a target; or these APIs return 400, 500 or empty results
avoid: To combine several sources into a review, start with literature-review; for simple queries that an existing dbtools function already covers, use that function
uses: bash, curl, python3 -m json.tool
chain: Downstream is target-assessment and clinicaltrials-landscape
---
## UniProt (REST, verified)
- With a known accession, fetch the entry directly: `curl -s "https://rest.uniprot.org/uniprotkb/P04637.json"`. Read `sequence.length`, `genes[0].geneName.value`, `comments` (type FUNCTION) and `uniProtKBCrossReferences`.
- Search by gene: `https://rest.uniprot.org/uniprotkb/search?query=gene_exact:TP53+AND+organism_id:9606+AND+reviewed:true&format=json&size=1`.
- The search endpoint sometimes returns HTTP 500. Switch to a direct lookup by accession first; if that also fails, retry once after a few seconds, and if it still fails, use a web search instead. Do not repeat the same request over and over.
- UniProt does not give chromosome positions; use Ensembl: `https://rest.ensembl.org/lookup/symbol/homo_sapiens/TP53?content-type=application/json`. Read `seq_region_name`, `start` and `end`.

## ClinicalTrials.gov v2 (verified)
```bash
curl -s -G "https://clinicaltrials.gov/api/v2/studies" --data-urlencode "query.intr=sotorasib OR adagrasib" --data-urlencode "filter.advanced=AREA[Phase]PHASE3" --data-urlencode "pageSize=50" --data-urlencode "fields=NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName"
```
- Parameters: `query.cond` (disease), `query.intr` (intervention or drug), `query.spons` (sponsor), `query.term` (any text). Use `filter.advanced=AREA[Phase]PHASE3` for phase; for phase II and III together, use PHASE2|PHASE3 and query both. Use `filter.overallStatus=RECRUITING` for status.
- Try both the generic name and the code name of a drug (sotorasib, AMG 510). Translate Chinese names into English first.
- If `nextPageToken` in the response is not empty, there is another page; fetch it with `pageToken=`. Add `countTotal=true` to get the total count in `countTotal`.
- List only registration numbers that were actually returned. A registration status is not the same as a trial's success.

## Open Targets (GraphQL, verified)
```bash
curl -s -X POST https://api.platform.opentargets.org/api/v4/graphql -H "Content-Type: application/json" -d '{"query":"{ target(ensemblId:\"ENSG00000169174\"){ approvedSymbol associatedDiseases(page:{index:0,size:5}){ rows{ disease{id name} score } } } }"}'
```
- You need the Ensembl gene ID first. For a gene symbol, use `https://rest.ensembl.org/lookup/symbol/homo_sapiens/PCSK9?content-type=application/json` and read `id`.
- Scores run from 0 to 1 and come back in descending order. When you write results, include the disease ID (MONDO_, EFO_ or HP_).
- For disease to target, use `disease(efoId:"...") { associatedTargets(...) }`.

## Quality bar
- When an API returns an error, read the error message, change the parameters and retry. If three different ways of calling the same API still fail, switch to another source and say so.
- Cite the source (the API address or the page link) and the query date for every result.
