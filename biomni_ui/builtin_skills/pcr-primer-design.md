---
title: PCR primer design
description: Design PCR primer pairs for a given DNA sequence (optionally limited to a target region) with Primer3, giving Tm, GC content and product size
category: Molecular & protein design
when_to_use: The user gives a template sequence and wants PCR, qPCR or sequencing primers, or wants to amplify around a given position
avoid: Multiplex PCR, cloning restriction sites and mutagenic primers are not covered (say that they need manual design); the sequence is shorter than the minimum product size; if there is no sequence, first get it from Ensembl or NCBI and check the species and version
uses: biomni_ui.analysis.design_primers, query_ensembl
chain: Upstream is obtaining the sequence; downstream must check specificity with Primer-BLAST
---
## Steps
1. Get the sequence and check its source: the gene or transcript ID, the species and the genome version. State whether the position coordinates are 0-based or 1-based.
2. Run:
```python
from biomni_ui.analysis import design_primers
seq = open("template.txt").read()
print(design_primers(seq, target_start=200, target_len=50, product_min=100, product_max=300, n=3))
```
   `target_start` and `target_len` define a region that the product must contain (0-based). Leave them out if there is no such region.
3. For each primer pair, give the sequences, Tm, GC%, and product size. Default parameters: length 18–25 nt, Tm 57–63 °C, GC 40–60%.
4. For qPCR, narrow the product to 70–150 bp. When designing from a cDNA sequence, prefer primers that span an exon junction, so that genomic DNA is not amplified.

## Quality bar
- **The function does not check specificity.** State clearly that the primers must be checked against the target species with NCBI Primer-BLAST before they are treated as ready to order.
- Warn about repeats, SNP sites and high-GC regions in the template.
- If no primers can be found, pass on the reason returned and suggest widening the product range or changing the region.

## Output conventions
- Table: number, forward primer, reverse primer, Tm (F and R), GC% (F and R), product size in bp.
- State explicitly: "to be verified with Primer-BLAST".
