---
title: Two-group analysis of 16S microbiome data
description: Compute alpha and beta diversity from a processed ASV or OTU table, combine several differential-abundance methods to judge consistency, and optionally infer function
category: Microbiome
when_to_use: The user has 16S amplicon data for two groups of samples and asks whether the microbiota differ between the groups, or which taxa differ most
avoid: Raw sequencing data must first be processed with QIIME2 or DADA2 (neither is installed on this computer); differential results are unstable with few samples; functional prediction is only an inference
uses: scikit-bio, scipy, ALDEx2, ANCOM-BC2, MaAsLin2
chain: Upstream is the ASV table and metadata; downstream can be functional enrichment
---
## Steps
1. Organise: the ASV count table (samples × taxa) and the metadata (groups and covariates). Rarefy to a common sequencing depth per sample, or check with rarefaction curves.
2. Alpha diversity: Shannon, Simpson and observed taxa count, compared between groups with the Mann–Whitney test.
3. Beta diversity: Bray–Curtis or UniFrac distances, with PERMANOVA to test the difference between groups.
4. Differential abundance: use the intersection of at least two methods (for example ANCOM-BC2 and ALDEx2) as the consistent result; flag taxa that are significant in only one method.
5. Functional inference (optional): a PICRUSt2-type tool; state that the results are predictions.

## Quality bar
- When sequencing depth differs widely, diversity estimates are biased; rarefy or use a suitable model.
- Handle zeros in sparse data for differential abundance (use CLR or the ANCOM approach).
- Correct for multiple groups and multiple tests.

## Output conventions
- Figures: PCoA plot, abundance boxplots of differential taxa.
- Table: alpha and beta test results, and the consistent list of differential taxa.
- State the sample count, the sequencing depth, the distance metric, the methods and the software versions.
