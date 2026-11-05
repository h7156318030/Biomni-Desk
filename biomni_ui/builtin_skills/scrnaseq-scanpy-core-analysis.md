---
title: Core single-cell RNA-seq analysis (Scanpy)
description: For single-cell data with raw counts, run quality control, normalisation, highly variable genes, PCA, UMAP, Leiden clustering and the marker genes of each cluster
category: Single-cell
when_to_use: The user has an h5ad file, a 10x .h5 file or an mtx folder, and wants a standard single-cell workflow and to see the cell clusters
avoid: The data have already been normalised or integrated and no raw counts remain; batch integration (multi-sample), trajectories, cell communication and RNA velocity are later steps and this skill does not do them; for very large data (more than 200,000 cells) that does not fit in memory, subsample first and say so
uses: biomni_ui.analysis.scrna_basic
chain: Downstream is cell type annotation, differential expression and enrichment
---
## Steps
1. Look at the data: the number of cells, the number of genes, whether the values are raw counts (integers), and whether mitochondrial genes (MT-) are present.
2. Run:
```python
from biomni_ui.analysis import scrna_basic
print(scrna_basic("sample.h5ad", out="scrna", min_genes=200, min_cells=3, max_mito=20.0, resolution=0.8))
```
3. Read the output: the number of cells before and after QC, the number of clusters, the cells per cluster, and the top 4 marker genes of each cluster. The UMAP is saved to `scrna_umap.png`, the markers to `scrna_markers.csv`, and the processed object to `scrna.h5ad`.
4. **You annotate the cell types yourself**, using marker genes and the literature. For each cluster, state the basis (which genes, which reference). If you are not sure, write "not annotated".

## Quality bar
- If too few cells remain after QC, the function reports an error: first check that the values are raw counts, then relax the thresholds.
- The mitochondrial threshold depends on the tissue (higher for heart and liver); state the threshold used.
- The resolution changes the number of clusters; when you report the number of clusters, state the resolution.
- The p values of the Wilcoxon marker test depend on the number of cells; a very small value does not mean large biological importance.

## Output conventions
- Start with the conclusion: how many cells, how many clusters, and the features of each cluster.
- Table: cluster | cells | marker genes | likely cell type (write only where there is a basis).
- List all the file names; state the parameters.
