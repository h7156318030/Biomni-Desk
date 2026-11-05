---
title: Ranking candidate disease genes for a single rare disease case
description: For one rare-disease case, rank candidate causal genes by strength of evidence (variant pathogenicity, phenotype match, gene constraint, literature and database evidence)
category: Genomics & genetics
when_to_use: The user has a patient's variant list and phenotype for a rare disease, and asks which gene is most likely causal or which variant matters most
avoid: This is a research aid and cannot replace clinical genetic counselling; the final judgement on variant pathogenicity must be made by a qualified specialist; phenotype data must be standardised (for example HPO terms)
uses: dbtools.query_clinvar, dbtools.gnomad_constraint, dbtools.query_monarch
chain: Upstream is the patient's VCF; downstream goes to variant-calling-from-sequencing and functional validation
---
## Steps
1. Organise the case: the patient's variants (gene, variant position, zygosity) and phenotypes (HPO terms).
2. Variant level: look up known interpretations in ClinVar. Down-weight variants with a high population frequency in gnomAD (above 1%).
3. Gene level: use gnomad_constraint to check gene constraint; highly constrained genes are more often linked to rare dominant diseases.
4. Phenotype match: use query_monarch to look up the gene–disease associations, and compare them with the patient's phenotypes.
5. Ranking: score each candidate gene on each line of evidence (pathogenic variant, phenotype match, constraint, literature) and give an evidence grade.

## Quality bar
- Avoid counting the same evidence twice for a gene with several lines of evidence.
- Check the review status of ClinVar interpretations (expert-reviewed interpretations carry more weight).
- For a candidate with no functional evidence, the conclusion can only be "possible".

## Output conventions
- Table: candidate gene, variant, ClinVar interpretation, frequency, constraint, phenotype match, evidence grade.
- State the case's phenotype list, the data versions and the date, and note: "Research aid; needs review by a specialist."
