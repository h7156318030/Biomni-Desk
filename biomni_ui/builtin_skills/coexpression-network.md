---
title: Gene co-expression network and modules (WGCNA approach)
description: Build a gene co-expression network from an RNA-seq expression matrix, find modules, relate modules to traits, and identify hub genes
category: Transcriptomics
when_to_use: The user asks which genes change together, wants gene modules related to a phenotype, or asks what the hub genes are; the input is an expression matrix with several samples
avoid: With fewer than about 15 samples the modules are unstable, and this must be stated; this is a correlation network, not a causal one; batch effects must be corrected first
uses: pandas, numpy, scipy; optionally the WGCNA package in R
chain: Upstream is the normalised expression from bulk-rnaseq-counts-to-de-deseq2; downstream can be enrichment of the modules with functional-enrichment-from-degs
---
## Steps
1. Take the expression matrix (genes × samples, normalised on a log scale), and keep the most variable genes (for example the top 5000):
```python
import numpy as np, pandas as pd
expr = pd.read_csv("log2_tpm.csv", index_col=0)
var = expr.var(axis=1).sort_values(ascending=False)
top = expr.loc[var.index[:5000]]
```
2. Calculate the correlations and convert them to a soft-thresholded adjacency (the WGCNA soft-threshold approach; β is chosen by a scale-free fit):
```python
corr = np.corrcoef(top.values)
beta = 6                          # choose by a scale-free topology fit (R^2 > 0.8); do not fix it
adj = np.abs(corr) ** beta
```
3. Hierarchical clustering gives the modules: apply `scipy.cluster.hierarchy.linkage` to 1 − adj, cut with `fcluster`, and drop very small modules (fewer than 30 genes).
4. Correlate each module's eigengene (the first principal component of the module) with the trait, and keep the significant modules. Within each module, rank genes by connectivity to find the hub genes.

## Quality bar
- Report the R² of the soft-threshold fit; a β chosen arbitrarily changes the modules.
- Correct the module-trait correlations for multiple testing; if you only report the most significant module, say so.
- Batch effects and differences in cell composition can create false co-expression modules; correct for them first, or check how the principal components relate to batch.

## Output conventions
- Table: module name, number of genes, correlation with the trait and p value, top 10 hub genes.
- State the number of samples, the number of variable genes, β, the clustering method and the data version.
