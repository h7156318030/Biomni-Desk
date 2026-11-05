---
title: Enrichment of genomic regions in public ChIP-seq peaks (ChIP-Atlas)
description: Test whether a set of genomic regions (such as differential peaks or SNP loci) is enriched in public ChIP-seq peak sets, and identify the related transcription factors or histone marks
category: Epigenomics
when_to_use: The user has a set of genomic regions and asks which transcription factor binding sites they overlap, or whether they are enriched in a class of enhancers
avoid: The genome build of the regions must match ChIP-Atlas; the choice of background regions determines the result; peak sets come from different experiments, so enrichment conclusions must be cautious
uses: pybedtools; ChIP-Atlas peak sets
chain: Upstream is differential peaks or GWAS loci; downstream goes to upstream-regulator-analysis
---
## Steps
1. Preparation: the target regions (BED format, hg38) and background regions (random regions of the same length, matched for GC content, at least 10 times as many).
2. Peak sets: choose the relevant peak sets from ChIP-Atlas (by transcription factor or histone mark, and by cell type).
3. Overlap counts: count the overlaps of the target and of the background with each peak set.
4. Enrichment test: for each peak set, use a hypergeometric or Fisher test to compare the overlap proportion of the target with that of the background, and calculate the fold enrichment.
5. Correct for multiple testing and list the significant peak sets.

## Quality bar
- The background must be matched to the target (GC content, gene density); otherwise the enrichment is an artefact.
- When the number of peaks differs widely between peak sets, normalise the fold enrichment.
- State the cell type for each result; do not generalise to all cells.

## Output conventions
- Table: peak set (transcription factor or mark, cell type), target overlap count, background overlap count, fold enrichment, FDR.
- State the sizes of the target and the background, the genome build, the ChIP-Atlas version and the date.
