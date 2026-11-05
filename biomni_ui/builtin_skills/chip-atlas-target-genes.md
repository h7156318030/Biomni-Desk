---
title: Known target genes of a transcription factor (ChIP-Atlas)
description: Retrieve the target genes that a transcription factor binds in public ChIP-seq experiments from ChIP-Atlas, and annotate the binding strength and the number of experiments
category: Epigenomics
when_to_use: The user asks which target genes a transcription factor has, or needs a target gene set for downstream enrichment
avoid: Target genes come from different cell types and experiments, and binding does not mean regulation; state the number of experiments and the range of cell types; requires network access
uses: the public ChIP-Atlas interface
chain: Upstream is the transcription factor name; downstream goes to upstream-regulator-analysis or chip-atlas-peak-enrichment
---
## Steps
1. Determine the standard symbol of the transcription factor (confirm it with uniprot_lookup).
2. Query the ChIP-Atlas target gene interface (by TF name and species, hg38 or mm10), and take the genes near the binding peaks.
3. Rank by peak strength (-log10 q value) and by the number of experiments, and list the top target genes.
4. Optional: group by cell type and compare how consistent the target genes are across cell types.

## Quality bar
- A target gene that appears in several experiments is more credible than one that appears in only one.
- For peaks outside promoters, say that enhancer regulation is possible.
- The result depends on which cell types the experiments covered; state that range.

## Output conventions
- Table: target gene, number of experiments with binding, maximum peak strength, range of cell types.
- State the ChIP-Atlas version, the species and the query date.
