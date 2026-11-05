---
title: Single-cell trajectories and direction of differentiation (pseudotime, RNA velocity)
description: Infer differentiation or disease-progression trajectories from single-cell data: pseudotime, branch structure, terminal states, and the direction given by RNA velocity
category: Transcriptomics
when_to_use: The user asks how cells differentiate, how cell states change during a disease, which terminal cells exist, or the direction of RNA velocity; the input is scRNA-seq data (h5ad or a count matrix)
avoid: RNA velocity cannot be done without splicing data (spliced and unspliced counts); a trajectory is an inference, not a real time series, so compare it with experimental time points before drawing conclusions
uses: scanpy, scvelo, palantir
chain: Upstream is the clustering result from scrnaseq-scanpy-core-analysis; downstream can be grn-pyscenic to infer regulators
---
## Steps
1. On already-clustered data, run PAGA first to get a coarse connectivity graph, then compute diffusion pseudotime:
```python
import numpy as np
import scanpy as sc
adata = sc.read_h5ad("clustered.h5ad")          # must already have neighbors and leiden
sc.tl.paga(adata, groups="leiden")
sc.pl.paga(adata, plot=False)
sc.tl.diffmap(adata)
root_cluster = "0"                                  # replace with a known stem or progenitor cluster (see step 2)
adata.uns["iroot"] = int(np.flatnonzero(adata.obs["leiden"].astype(str).values == root_cluster)[0])
sc.tl.dpt(adata)
print(adata.obs["dpt_pseudotime"].describe())
```
2. Do not choose the root (starting point) arbitrarily. Use known stem or progenitor marker genes (such as CD34 or SOX2) to find the cluster with the highest expression, and tell the user what the choice was based on.
3. When splicing counts are available, run RNA velocity (scvelo):
```python
import scvelo as scv
scv.pp.filter_and_normalize(adata, min_shared_counts=20)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)
scv.tl.velocity(adata, mode="stochastic")
scv.tl.velocity_graph(adata)
scv.tl.latent_time(adata)
```
4. Terminal states: the clusters that are sinks in the velocity graph, or the ends of branches with degree 1 in PAGA.

## Quality bar
- The direction of pseudotime is set by the root; a wrong root makes every direction wrong, so state in the answer what the root was based on.
- Velocity is unreliable when data quality is poor or the proportion of spliced reads is low; report the velocity confidence (velocity_confidence).
- A trajectory branch is a model result. Support it with changes in marker-gene expression along the branch; do not rely on the plot alone.

## Output conventions
- Figures: PAGA graph, UMAP coloured by pseudotime, and (if available) the velocity streamline plot.
- Table: the clusters of each terminal state, their cell counts, and representative marker genes.
- State the basis for the root, the number of cells, the filter thresholds and the software versions.
