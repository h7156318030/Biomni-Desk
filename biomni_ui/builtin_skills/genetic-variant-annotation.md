---
title: Genetic variant annotation and clinical significance
description: For one variant or a batch of variants (rsID, HGVS, coordinates), look up the functional consequence, ClinVar clinical significance, population frequency and the gene's constraint
category: Genomics & genetics
when_to_use: The user gives a variant and wants to know whether it is pathogenic, how common it is in the population, or what it does to the protein; or wants a summary of the known pathogenic variants of a gene
avoid: Clinical diagnosis or genetic counselling (only summaries of public data can be provided, not a diagnostic opinion); calling variants from FASTQ or BAM files (there is no pipeline for this on this computer); if the genome build is unknown, ask first
uses: query_ensembl, query_clinvar, query_dbsnp, biomni_ui.dbtools.gnomad_constraint, query_gnomad
chain: Upstream is a sequencing report; downstream is a report with charts
---
## Steps
1. **Fix the coordinate system first**: the genome build (GRCh38 or GRCh37), the transcript (such as NM_ or ENST) and the HGVS notation. A wrong build places the variant somewhere else.
2. Functional consequence: `query_ensembl(prompt="VEP for ENST00000269305.9:c.817C>T")` (the Ensembl VEP HGVS interface).
3. Clinical significance: `query_clinvar(prompt="clinical significance of rs28934578")`. Read out the classification (pathogenic, likely pathogenic, uncertain significance, likely benign or benign), the review status (stars), the conditions, and whether there are conflicts.
4. Population frequency: `query_gnomad(prompt="allele frequency of 17-7675088-C-T")`. The variant ID is chromosome-position-reference-alternate, GRCh38.
5. Gene level:
```python
from biomni_ui.dbtools import gnomad_constraint
print(gnomad_constraint("TP53"))
```

## Quality bar
- When the ClinVar review status is low (0 to 1 stars) or there are conflicts, the classification is not settled.
- A common variant (for example above 1%) is usually not a highly penetrant cause of a rare disease; point this out.
- For a "variant of uncertain significance" (VUS), do not steer the reader toward either pathogenic or benign.
- State the database and the version or date for each piece of evidence.

## Output conventions
- A small table for each variant: position and consequence, ClinVar classification and stars, gnomAD frequency, gene constraint. End with one sentence on the direction of the evidence.
- Standard statement: "A summary of public data; not a diagnosis."
