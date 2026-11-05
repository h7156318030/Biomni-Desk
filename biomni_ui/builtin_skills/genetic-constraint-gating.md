---
title: Gene functional constraint and knockout tolerance (gnomAD)
description: Use gnomAD's pLI, LOEUF and missense and loss-of-function z scores to judge whether a gene is sensitive to loss-of-function variants, for target safety and knockout-tolerance assessment
category: Genomics & genetics
when_to_use: The user asks whether this gene can be knocked out, whether targeted inhibition could be fatal, or whether the gene has functional constraint in the population; or wants to pick tolerant targets from a gene list
avoid: Constraint metrics only describe the distribution of variants in the population; they do not establish disease mechanism or drug efficacy, and they cannot judge the pathogenicity of an individual patient's variant
uses: biomni_ui.dbtools.gnomad_constraint
chain: Upstream is often a target list or disease associations; downstream can be tissue expression specificity, for an overall safety judgement
---
## Steps
1. Get the constraint metrics for a gene symbol:
```python
from biomni_ui.dbtools import gnomad_constraint
print(gnomad_constraint("CD19"))
```
   The output includes pLI, LOEUF, the expected and observed numbers of loss-of-function variants, the missense z score and the loss-of-function z score, with a one-sentence reading.
2. Grade by thresholds (common criteria; state the version you used):
   - pLI ≥ 0.9 or LOEUF < 0.35: strong constraint. Loss-of-function variants are rare in the population, so knockout or strong inhibition needs caution.
   - 0.35 ≤ LOEUF < 0.6: moderate constraint.
   - LOEUF ≥ 0.6 or pLI < 0.1: weak constraint. Loss-of-function variants are tolerated.
3. Give the graded result to the user for their decision; do not state a "safe" or "unsafe" conclusion yourself.

## Quality bar
- LOEUF is a more stable metric than pLI. When the two disagree, rely on LOEUF and say so.
- Confirm the gene symbol first with `uniprot_lookup` or `resolve_aliases`; an old symbol may return a different gene.
- When a gene has several transcripts, gnomAD's metrics use the canonical transcript; say so.
- Weak constraint shows only that the population tolerates loss of the gene; it does not show that the gene is free of toxicity when a drug targets it.

## Output conventions
- Table: metric, value, threshold grade, reading.
- State the data source (gnomAD), the version, the gene symbol and the query date.
