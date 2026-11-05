---
title: Gene regulatory networks and cell regulons (pySCENIC)
description: Use pySCENIC to infer transcription factor regulatory networks from scRNA-seq, and compute each cell's regulon activity
category: Transcriptomics
when_to_use: The user asks which transcription factors drive cell states, or what the regulons of a cell type are
avoid: pySCENIC needs species-specific databases (genome-wide rankings and motifs), which must be downloaded; network inference needs enough cells (several hundred or more); regulon activity is an inference only
uses: pyscenic and arboreto; scanpy
chain: Upstream is the QC and normalised matrix from scRNA-seq; downstream goes to upstream-regulator-analysis
---
## Steps
1. Input: a normalised expression matrix (cells × genes), with lowly expressed genes already filtered out.
2. Co-expression network: use GRNBoost2 from arboreto to infer transcription factor and target gene pairs.
3. Regulons: prune the network with motif enrichment (cisTarget databases), keeping the target genes that are supported by a motif.
4. Activity: calculate each cell's regulon activity with AUCell.
5. Results: compare regulon activity across cell types, and find the regulons that are specific to each type.

## Quality bar
- The database version must match the species and the genome build.
- Check regulon activity against known marker genes.
- With few cells the network is unstable; say so.

## Output conventions
- Figures: heatmap and UMAP of regulon activity.
- Table: regulon, number of target genes, cell-type specificity.
- State the database version, the species, the parameters and the date.
