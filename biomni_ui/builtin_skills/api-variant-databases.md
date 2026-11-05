---
title: Variant database recipes (ClinVar, gnomAD, VEP, dbSNP)
description: Correct ways to query variants with curl through the NCBI E-utilities, the gnomAD GraphQL API, Ensembl VEP and dbSNP, including how to find the right gnomAD variant ID
category: Genomics & genetics
when_to_use: You need a variant's clinical classification in ClinVar, its population frequency in gnomAD, or its functional consequence in Ensembl (the variant may be given as HGVS, an rsID or coordinates), or these APIs returned "not found", 400 or empty results
avoid: Clinical diagnosis; querying before the genome build is known (first decide GRCh38 or GRCh37); use dbtools functions instead when they already cover the query
uses: bash, curl, python3 -m json.tool
chain: Downstream is genetic-variant-annotation for the summary and report
---
## ClinVar (NCBI E-utilities, verified)
1. Search: query by gene and exact variant name; do not search with plain language only.
```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term=BRCA1%5Bgene%5D+AND+c.5266dup%5BVariant+name%5D&retmode=json"
```
   - Write HGVS as `c.5266dup` (not dupC). You can also search by rsID: `term=rs334`. Old names (such as 5382insC) often return nothing; use HGVS instead.
2. Summary: `esummary.fcgi?db=clinvar&id=17677&retmode=json`. Read `result.<id>.title`, `germline_classification.description` (the classification), `review_status` (the review status) and `variation_set[0].variation_loc` (GRCh38 and GRCh37 coordinates).
3. Page link: `https://www.ncbi.nlm.nih.gov/clinvar/variation/<id>/`. The id is the number esearch returns; the accession VCV000017677 corresponds to 17677.

## gnomAD (GraphQL, verified): query the region first, then find the variant by position and allele
Variant IDs are easy to write wrongly. **For insertions and deletions, use the left-aligned VCF form with one anchor base.** For example, BRCA1 c.5266dup (GRCh38) is `17-43057062-T-TG`, not `G-GC` and not `GGG-GGGG`. Do not guess IDs; query the region to list the nearby variants and then find the one you need.
```bash
curl -s -X POST https://gnomad.broadinstitute.org/api -H "Content-Type: application/json" -d '{"query":"{ region(chrom:\"17\", start:43057050, stop:43057080, reference_genome:GRCh38){ variants(dataset: gnomad_r4){ variant_id pos ref alt genome{ac an} exome{ac an} } } }"}'
```
- Take the coordinates from ClinVar (the start and stop in `variation_loc`) and widen the window by about 15 bp on each side.
- In the response, find the row where `pos` equals the position and `alt` is longer than `ref` (an insertion) or shorter (a deletion). The `ac` and `an` values under `genome` and `exome` add up to the allele count and the sample number; frequency = (ac_genome + ac_exome) / (an_genome + an_exome). Either of the two may be null.
- For GRCh37, use `reference_genome:GRCh37` and `dataset: gnomad_r2_1`, with GRCh37 coordinates.
- Single-variant query: `variant(variantId:"17-43057062-T-TG", dataset: gnomad_r4){ variant_id genome{ac an} exome{ac an} }`. The ID must be right to return a result. `Variant not found` means the ID is written wrongly, not that the variant is absent from the database.

## Ensembl VEP (REST, verified)
```bash
curl -s -X POST https://rest.ensembl.org/vep/human/hgvs -H "Content-Type: application/json" -H "Accept: application/json" -d '{"hgvs_notations":["NM_007294.4:c.5266dup"]}'
```
- The key must be `hgvs_notations`. Writing `hgvs` returns the error "Cannot find hgvs_notations key".
- Read `transcript_consequences[].consequence_terms`, `impact`, `amino_acids` and `hgvsp`. `most_severe_consequence` gives the most severe consequence.
- For an rsID, use `GET https://rest.ensembl.org/vep/human/id/rs334?content-type=application/json`.

## dbSNP
`curl -s "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/334"` returns the merge history and `primary_snapshot_data` (position, alleles and annotation).

## Quality bar
- Before you report a frequency, you must have found that row in the response. If you cannot find it, say which ways of writing the ID you tried; do not write "no record in gnomAD".
- When you report the ClinVar classification, also report the review status. A low or conflicting review status means the classification is not settled.
- Cite the API address or the page link as the source, and the query date as the day you ran it.
