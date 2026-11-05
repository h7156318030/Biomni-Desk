---
title: Cell-type proportion deconvolution of bulk tissue (bulk RNA-seq)
description: Estimate the proportion of each cell type in bulk RNA-seq samples, using cell-type signatures from a single-cell reference, and compare the proportions between groups
category: Transcriptomics
when_to_use: The user asks about the proportion of immune cells in samples, differences in cell composition between disease and control groups, or the composition of the tumour microenvironment, and has a single-cell reference or usable signature genes
avoid: Without a suitable single-cell reference the results are unreliable; estimates for rare cell types have large errors; proportions are relative values, not absolute cell numbers
uses: scipy; optionally BayesPrism or DWLS
chain: Upstream is single-cell-census-query or a reference signature from scRNA-seq; downstream is the between-group statistics
---
## Steps
1. Build a signature for each cell type from the single-cell reference (the mean expression per type, keeping genes that discriminate well):
```python
import pandas as pd, numpy as np
ref = pd.read_csv("celltype_mean_expression.csv", index_col=0)   # genes × cell types
markers = []
for ct in ref.columns:
    others = ref.drop(columns=ct).max(axis=1)
    diff = ref[ct] - others
    markers += diff.sort_values(ascending=False).index[:50].tolist()
markers = sorted(set(markers) & set(bulk.index))                  # bulk is genes × samples
```
2. Estimate each sample's proportions with non-negative least squares, then normalise them to sum to 1:
```python
from scipy.optimize import nnls
A = ref.loc[markers].values
props = []
for s in bulk.columns:
    x, _ = nnls(A, bulk.loc[markers, s].values)
    props.append(x / x.sum())
props = pd.DataFrame(props, index=bulk.columns, columns=ref.columns)
```
3. Compare the groups: test each cell type's proportions with a non-parametric test (Mann–Whitney) and correct for multiple testing.

## Quality bar
- Deconvolution can only estimate cell types that are in the reference; a cell type missing from the reference is wrongly assigned to similar types.
- When proportions are strongly correlated (for example T-cell subsets), state that the resolution is limited.
- Report the reference source, the number of reference cells and the gene selection criteria; check the NNLS results against the known trends of marker cells.

## Output conventions
- Table: sample by cell-type proportions; for the between-group comparison, medians, p values and corrected p values.
- State the reference dataset, the cell-type definitions, the number of marker genes and the method (NNLS, BayesPrism or similar).
