---
title: Single-cell ATAC and multi-omics (snATAC, 10x Multiome)
description: Process scATAC-seq or 10x Multiome data: fragment quality control, LSI dimension reduction and clustering, MACS3 peaks, gene activity and differential accessibility
category: Epigenomics
when_to_use: The user has single-cell chromatin accessibility data (fragment files, or Cell Ranger ATAC or ARC output), and asks about the regulatory regions of cell types or differentially accessible regions
avoid: Needs a fragment file (fragments.tsv.gz); re-calling peaks depends on MACS3 (must be installed); gene activity is only a proxy for accessibility, not for expression
uses: snapatac2 or ArchR, scanpy, MACS3
chain: Upstream is the Cell Ranger ATAC or ARC output; downstream goes to grn-pyscenic or integration with transcriptomics
---
## Steps
1. Fragment quality control: unique fragments per cell, TSS enrichment and nucleosome signal. Filter out low-quality cells.
2. Dimension reduction: TF-IDF followed by singular value decomposition (LSI). Drop the first component, which correlates with depth.
3. Clustering and visualisation: use the first 20 to 30 LSI components to build a neighbour graph, then Leiden clustering and UMAP.
4. Peaks and gene activity: call peaks with MACS3 on pseudo-bulk profiles of each cluster. Gene activity is the accessibility of the gene body weighted with the upstream region.
5. Differential accessibility: test between clusters with pseudo-bulk or cell-level tests, find the differential regions, and annotate them with their nearest genes.

## Quality bar
- Cells with low TSS enrichment or few fragments are unreliable and must be filtered out.
- Check the correlation between gene activity and expression; do not treat them as identical.
- Check for batch effects after LSI.

## Output conventions
- Figures: UMAP, TSS enrichment plot, fragment size distribution.
- Table: marker accessible regions for each cluster and their nearest genes.
- State the quality-control thresholds, the cell and peak numbers, the software versions and the date.
