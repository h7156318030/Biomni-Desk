---
title: Core single-cell RNA-seq analysis (Seurat, R workflow)
description: Run a complete scRNA-seq analysis with Seurat: QC, normalisation, integration, clustering, marker genes and cell type annotation
category: Transcriptomics
when_to_use: The user prefers R or already has a Seurat object, and wants a complete workflow from raw counts to cell types
avoid: Seurat needs an R environment; if R or Seurat is not installed on this computer, use scrnaseq-scanpy-core-analysis (the Python version, with the same workflow); watch memory for large datasets
uses: Seurat, SeuratObject; harmony or SCTransform for integration, optionally
chain: Equivalent to scrnaseq-scanpy-core-analysis; choose one of the two. Downstream goes to trajectory, communication and integration analyses
---
## Steps
1. Read in: load the count matrix with Read10X and create a Seurat object, filtering on the minimum number of genes and cells.
2. QC: calculate the mitochondrial and ribosomal fractions, and filter on gene count, UMI count and mitochondrial fraction.
3. Normalisation: SCTransform (or LogNormalize), then select the highly variable genes.
4. Dimension reduction and integration: PCA. If there are batches, integrate with Harmony or CCA.
5. Clustering: FindNeighbors and FindClusters (try resolutions from 0.4 to 1.0).
6. Markers and annotation: FindAllMarkers (Wilcoxon, filtered on logFC and the fraction of cells expressing), then annotate cell types with known markers.

## Quality bar
- Set the filter thresholds from the distribution of the data, and report the number of cells retained.
- After integration, check for over-integration (different biological states merged together).
- Annotations must be supported by marker genes; do not rely on the clustering alone.

## Output conventions
- Figures: UMAP, violin plots, dot plot of marker genes.
- Table: the marker genes of each cluster and the basis for its annotation.
- State the Seurat version, the filter thresholds, the integration method, the resolution and the date.
