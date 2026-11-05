---
title: Disease-associated target ranking (Open Targets)
description: For a disease, get the targets associated with it, with the overall association score and the top targets; use this to find candidate targets starting from a disease
category: Drug discovery & safety
when_to_use: The user asks which candidate targets a disease has, which genes are associated with a disease, or how strong the evidence linking a target to a disease is
avoid: The query parameter of the interface is a disease name or disease identifier, not a gene name; with a gene name, the results may match an unrelated disease, so you must first check which disease was matched
uses: biomni_ui.dbtools.open_targets
chain: Upstream is the disease name; downstream goes to druggability (target-tractability-druggability) and tissue expression (tissue-expression-specificity)
---
## Steps
1. Get the associated targets for a disease name:
```python
from biomni_ui.dbtools import open_targets
print(open_targets("B-cell acute lymphoblastic leukemia"))
```
   The first line of the output gives the matched disease and its MONDO identifier, and the total number of associated targets. After that come the top 15 genes, their names and their overall association scores.
2. First check that the disease in the first line is the one the user means. If it is not, use a more specific disease name, or query again with the MONDO identifier directly.
3. For the candidate targets, run the druggability and tissue-expression skills for the next screening step.

## Quality bar
- The overall association score combines several data sources; it is not causal evidence. State the main contributing sources (genetics, literature, expression and so on).
- If the disease name is wrong, the results will be biased. For example, a gene name used as the query can match a disease, so check step 2.
- For rare diseases or subtypes, use standard terms (MONDO or EFO), not colloquial names.

## Output conventions
- Table: gene, name, overall association score, druggability (if checked).
- State the disease name and MONDO identifier, the data version and the query date.
