---
title: Spatial transcriptomics analysis (Visium and Xenium)
description: Process spatial transcriptomics data: quality control, clustering and spatially variable genes, with separate workflows for Visium (spot level) and Xenium (single-cell level)
category: Transcriptomics
when_to_use: The user provides spatial transcriptomics data (Visium spot data, or Xenium transcript data) and asks which genes are expressed in which spatial regions, or which genes vary spatially
avoid: If the input type is unclear, confirm it first (Visium and Xenium need different workflows); spatial interpretation is weak without the tissue image; cell segmentation is not done here
uses: scanpy, squidpy
chain: Upstream is the raw spaceranger or Xenium output; downstream goes to cell type annotation and spatial neighbourhood analysis
---
## Steps
1. Confirm the data type: Visium output contains a `spatial/` folder and the tissue image; Xenium output is a table of transcript coordinates. The two cannot be processed with the same workflow.
2. Basic Visium workflow:
```python
import scanpy as sc, squidpy as sq
adata = sc.read_visium("spaceranger_output/")
adata.var_names_make_unique()
sc.pp.filter_genes(adata, min_cells=10)
sc.pp.normalize_total(adata); sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.pca(adata); sc.pp.neighbors(adata); sc.tl.leiden(adata)
sq.gr.spatial_neighbors(adata)
sq.gr.spatial_autocorr(adata, mode="moran", genes=adata.var_names[adata.var["highly_variable"]][:500])
```
3. Xenium: transcripts are counted by coordinates into cells or grid bins, and then processed with the scRNA workflow. Negative control probes are used to estimate background.
4. Spatially variable genes: rank by Moran's I, and report the genes that are significant after FDR correction.

## Quality bar
- A Visium spot contains several cells, so it cannot be interpreted as a single cell.
- Filter out or flag spots in the background and at the tissue edge.
- The significance of spatial autocorrelation must be corrected, and the number of genes and spots must be stated.

## Output conventions
- Figures: spatial cluster map, spatial expression maps of representative genes.
- Table: spatially variable genes (Moran's I, FDR).
- State the data type, the number of spots or cells, the filter thresholds and the software versions.
