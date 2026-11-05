---
title: Cell-cell communication (ligand-receptor, single-cell)
description: Infer ligand-receptor communication between cell types from scRNA-seq, then visualise it as a network and test it for differences
category: Transcriptomics
when_to_use: The user asks which cell types communicate through which signals, or how communication changes in a disease
avoid: Communication is an expression-based inference, not a measurement of signalling; the ligand and receptor must be expressed in the same sample; small subtypes and cell populations give unstable results
uses: liana or CellChat; scanpy
chain: Upstream is cell type annotation (scrnaseq-scanpy-core-analysis); downstream is a comparison between disease and control groups
---
## Steps
1. Cell type annotation: drop or merge cell types with too few cells (fewer than 30).
2. Communication inference: use a ligand-receptor database (such as CellChatDB) to score the communication between each pair of cell types (the product of mean ligand and receptor expression, tested by random permutation).
3. Filtering: keep only communications that are significant (p < 0.05) and expressed in a reasonable fraction of cells on both sides.
4. Network: draw a network with each cell type's outgoing and incoming strength.
5. Comparison: changes in communication between disease and control, summarised by pathway.

## Quality bar
- Results for small cell populations are unstable; flag them.
- The presence of a ligand and a receptor does not mean that signalling occurs; check the downstream genes of the pathway as well.
- Fix the random seed for the permutations and report it.

## Output conventions
- Figures: communication network, heatmap (cell-type pairs by pathway).
- Table: ligand-receptor pair, source cell, target cell, strength, p value.
- State the database version, the number of permutations, the filter thresholds and the date.
