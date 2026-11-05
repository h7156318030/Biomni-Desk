---
title: Multimodal integration of paired CITE-seq (RNA plus surface protein)
description: Integrate the RNA and antibody-derived tag (ADT) data of CITE-seq: quality control for each modality, ADT normalisation (dsb or CLR), weighted nearest neighbour integration, and differential protein analysis
category: Multi-omics
when_to_use: The user has paired single-cell RNA and surface protein data, and asks whether surface proteins can separate cell types or whether RNA and protein agree
avoid: ADT data have high background noise, which must be corrected; the cells of the two modalities must correspond one to one; check that the integrated clustering is not over-integrated
uses: scanpy, muon or mudata, dsb
chain: Upstream is the QC from scrnaseq-scanpy-core-analysis; downstream goes to cell type annotation
---
## Steps
1. Quality control per modality: filter RNA by mitochondrial fraction and gene count, and filter ADT by total counts and background (empty droplets).
2. ADT normalisation: dsb (using empty droplets to estimate background), or CLR (centred by the geometric mean of each feature).
3. Integration: weighted nearest neighbour (WNN) combines the two modalities into a single neighbour graph and clustering.
4. Check: whether the RNA and protein markers correspond (for example the CD3 protein against the CD3E gene).
5. Differential proteins: compare between replicates (pseudobulk), using biological replicates rather than cell counts.

## Quality bar
- If background noise is not corrected, the boundary between positive and negative cells is wrong.
- After integration, check for cell types that are over-merged or over-split, and compare with the single-modality results.
- Differential analysis must use samples (replicates) as the unit.

## Output conventions
- Figures: WNN UMAP, distribution plots of ADT.
- Table: the RNA and protein markers of each cluster, and the list of differential proteins.
- State the QC thresholds, the normalisation method, the integration parameters and the date.
