---
title: Variant information lookup (ClinVar and population frequency)
description: Look up the clinical significance in ClinVar and the population frequency in gnomAD for a gene or variant, and organise the results
category: Genomics & genetics
when_to_use: The user asks about the pathogenic variants of a gene, the clinical significance of a specific variant, or its population frequency
avoid: When a formal clinical variant classification or a diagnostic conclusion is needed; this workflow only organises information and does not replace ACMG/AMP classification or clinical judgement
uses: query_clinvar, query_gnomad, query_ensembl
chain: You can first use query_ensembl to confirm the gene coordinates and transcripts
---
## Steps
1. Confirm the gene symbol, the species and the genome build (human GRCh38 by default); if needed, first look up the coordinates in Ensembl.
2. Query the gene or variant with `query_clinvar`. Count the entries in each clinical significance class (pathogenic, likely pathogenic, uncertain significance, benign and so on), and record the review status.
3. Query the population frequency with `query_gnomad`. State the version of the dataset used.
4. Summarise in a table: variant, clinical significance, review status, population frequency, source link.

## Output conventions
- A table, plus a text summary of no more than three sentences.
- State clearly: the data sources and the query time, and the basis of the counts (whether conflicting interpretations are included).
- End with the note "For information only; not a medical diagnosis or clinical advice".

## Notes
- ClinVar entries are updated, so the counts change over time; do not present a count as a fixed fact.
- A frequency of zero does not mean that a variant is rare or pathogenic; do not conclude that from it.
