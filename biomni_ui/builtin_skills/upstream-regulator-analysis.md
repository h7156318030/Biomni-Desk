---
title: Upstream regulator analysis (transcription factors and DE genes)
description: Use binding evidence from ChIP-Atlas, together with differentially expressed genes, to find transcription factors that may drive these changes
category: Multi-omics
when_to_use: The user has differential expression results and asks which transcription factors are driving the changes
avoid: The binding evidence from ChIP-Atlas comes from different cell types, and binding is not regulation; when transcription factors are highly correlated, say so
uses: the ChIP-Atlas target gene interface, scipy
chain: Upstream is the DE results; downstream goes to grn-pyscenic or functional validation
---
## Steps
1. Take the DE genes: list the up-regulated and down-regulated genes separately, with FDR < 0.05 and |log2FC| > 1.
2. For each transcription factor, get its target gene set with chip-atlas-target-genes.
3. Enrichment: for each transcription factor, count the overlap between its target genes and the DE genes, and test it with a hypergeometric test, using as background all the genes that were detected.
4. Direction: among the target genes of a transcription factor, the ratio of up-regulated to down-regulated genes indicates whether it is likely to act as an activator or a repressor.
5. Ranking: take the transcription factors that are significant after correction, and list their overlapping genes.

## Quality bar
- The background gene set must be the genes actually detected, not the whole genome.
- The cell types of the binding evidence must match the samples.
- Cluster correlated transcription factors to remove redundancy in the results.

## Output conventions
- Table: transcription factor, number of target genes, overlap count, p value, FDR, direction.
- State the DE thresholds, the number of background genes, the ChIP-Atlas version and the date.
