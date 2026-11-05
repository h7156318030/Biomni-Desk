---
title: Single-cell QC scorecard for cell therapy products (CAR-T, CAR-NK, iPSC)
description: Release testing of scRNA-seq batches of cell therapy products: identity and purity, residual pluripotency, off-target lineages and maturity, with a scorecard
category: Transcriptomics
when_to_use: The user wants to assess the quality of one or more batches of a cell therapy product, or asks whether a batch can be released or whether two batches are comparable
avoid: Release decisions must be made by quality assurance under the regulatory requirements; this only gives technical scores; state how the reference lineages were chosen
uses: scanpy, pandas; the reference atlas must be downloaded
chain: Upstream is the QC from scrnaseq-scanpy-core-analysis; downstream goes to the product definition in cell-therapy-car-design
---
## Steps
1. Identity and purity: expression of marker genes (for example CD3E and the CD19 CAR), and the fraction of the target cell type.
2. Residual pluripotency: the fraction of cells expressing pluripotency markers (POU5F1, NANOG); set a threshold.
3. Off-target lineages: the fraction of non-target lineages (such as fibroblast and epithelial).
4. Maturity and exhaustion: the fraction of cells expressing exhaustion markers (PDCD1, HAVCR2, LAG3).
5. Scorecard: pass or fail for each item, with an overall grade; compare batches against the same reference.

## Quality bar
- Define the thresholds in advance and record their source; do not adjust them afterwards.
- Sample size and cell number affect how reliable the fractions are; report confidence intervals.
- Release decisions must be made by qualified personnel.

## Output conventions
- Table: metric, threshold, observed value, pass or fail.
- State the batch identifier, the number of cells, the reference dataset, the source of the thresholds and the date.
