---
title: Drug target assessment (association, druggability, expression, genetic constraint)
description: For one gene or target, summarise its Open Targets disease associations, druggability, GTEx tissue expression, gnomAD loss-of-function constraint and protein interactions, and give the supporting evidence and the risks
category: Drug discovery & safety
when_to_use: The user asks whether a gene is worth pursuing as a target, which diseases it is linked to, whether it is druggable, or in which tissues it is expressed and how safe targeting it would be; or wants to rank the targets for a disease
avoid: For only the basic function of a gene, use the UniProt skill; molecular docking or structure prediction is not possible here; when the conclusion goes into a regulatory submission, note that this skill is an early assessment and not an evidence grading
uses: biomni_ui.dbtools.open_targets, biomni_ui.dbtools.target_tractability, biomni_ui.dbtools.gtex_expression, biomni_ui.dbtools.gnomad_constraint, biomni_ui.dbtools.string_interactions
chain: Downstream goes to ChEMBL compound search, ClinicalTrials registration search and a report with charts
---
## Steps (each call takes 1–3 seconds, so they can run together)
```python
from biomni_ui.dbtools import open_targets, target_tractability, gtex_expression, gnomad_constraint, string_interactions
gene = "PCSK9"
print(open_targets(gene, "target", 15))      # the strongest disease associations
print(target_tractability(gene))             # druggability labels for small molecules, antibodies, PROTACs and so on, plus the number of known drugs
print(gtex_expression(gene, 12))             # tissue expression (median TPM)
print(gnomad_constraint(gene))               # LOEUF and pLI: clues on the safety of inhibiting the gene
print(string_interactions(gene, 10))         # interacting proteins
```
To rank targets for a disease: `open_targets("thalassemia", "disease", 20)`.

## How to read the results
- **The association score** (0 to 1) is a combined evidence score, not an effect size. Only scores above 0.9 count as very strong. To list the evidence types behind a score, check the Open Targets page; do not make them up.
- **Druggability**: "Approved Drug" or "Advanced Clinical" means drugs already exist. "Structure with Ligand" or "High-Quality Pocket" means a small molecule is feasible. For antibodies, look at "UniProt loc high conf" (membrane proteins). With no labels at all, the evidence is insufficient, which **does not mean the target is undruggable**.
- **Expression**: if the highest tissue accounts for more than 40% of the total, treat it as tissue-specific. A target expressed broadly in vital organs (heart, brain) calls for caution about off-target toxicity.
- **Constraint**: LOEUF below 0.35 means strong constraint (a risk for inhibitors); above 0.6 means better tolerance. pLI is only a reference.

## Quality bar
- Check the gene name (the human gene symbol). For a gene with an ambiguous name (such as MET), confirm that it is the human gene.
- State the source database and the date for each conclusion; databases are updated.
- Where a database has no information, write "not in this database"; do not fill the gap.

## Output conventions
- Conclusion card: supporting evidence (disease associations, existing drugs), risks (constraint, broad expression, known failures), and what is still missing.
- Data table: one row of key numbers per database, with the source.
