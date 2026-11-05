---
title: Differential peaks between two groups of ChIP-seq or ATAC samples (ChIP-Atlas comparison)
description: Compare the differential peaks or differentially methylated regions between two groups of epigenomic experiments (such as treated and control ChIP-seq, ATAC-seq, DNase-seq or methylation data)
category: Epigenomics
when_to_use: The user has data from two groups of epigenomic experiments, or ChIP-Atlas experiment IDs, and asks which regions differ in binding or accessibility between the groups
avoid: With fewer than two pairs of samples the statistical power is weak; batch and sequencing depth must be handled first; the biological meaning of differential peaks should be interpreted after gene annotation
uses: peak and count matrices, DESeq2 or pydeseq2
chain: Upstream is the aligned BAM or peak files; downstream goes to gene annotation and upstream-regulator-analysis
---
## Steps
1. Collect the two groups: at least two biological replicates per group; record the experiment type and cell line.
2. Unify the peak set: merge the peaks of both groups, and count the reads in peaks for each region in each sample.
3. Differential analysis: compare the groups on the counts with DESeq2 or pydeseq2, controlling for sequencing depth.
4. Annotation: the gene nearest to each differential region (by TSS distance).
5. Report: the number of regions that go up and down, and the main gene annotations.

## Quality bar
- With few samples, state clearly that the differential results have low statistical power.
- When sequencing depth differs widely, normalise for depth or include it as a covariate.
- Linking a region to a gene by nearest neighbour is only an approximation; say so.

## Output conventions
- Table: differential region, log2FC, p value, FDR, nearest gene.
- State the experiment IDs, the number of samples, how the peak set was built, the thresholds and the date.
