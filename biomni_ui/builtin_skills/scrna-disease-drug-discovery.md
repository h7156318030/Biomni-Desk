---
title: From disease single-cell analysis to target prioritisation (combining scRNA-seq and human genetics)
description: Combine the disease's single-cell cell states with human genetic evidence to prioritise therapeutic targets for the disease
category: Transcriptomics
when_to_use: The user has scRNA-seq data from a disease and wants to find genes that could serve as drug targets
avoid: A correlation between cell types in single-cell data is not causation; genetic evidence must match the disease; target priorities are only candidates and need experimental validation
uses: scrnaseq-scanpy-core-analysis, dbtools.open_targets, dbtools.target_tractability, dbtools.gtex_expression
chain: Upstream is the scRNA-seq data; downstream goes to target-tractability-druggability and direction-of-effect-concordance
---
## Steps
1. Cell states: single-cell analysis of disease and control, to find the cell types that expand or are specific to the disease.
2. Differential genes: within the disease-related cell types, the genes differentially expressed between disease and control.
3. Genetic evidence: for these genes, their association with the disease in open_targets, and the genetic evidence behind it.
4. Druggability and safety: target_tractability and gtex_expression.
5. Overall ranking: score five criteria (cell specificity, size of the difference, genetic evidence, druggability, normal-tissue risk), and rank.

## Quality bar
- Validate cell specificity with sample replicates; do not rely on cell counts alone.
- State whether the genetic evidence is only an association.
- Priorities are candidates only; they need functional experiments to validate them.

## Output conventions
- Table: gene, cell type, size of difference, genetic evidence, druggability, normal-tissue risk, overall score.
- State the dataset, the number of cells, the number of samples, the thresholds and the date.
