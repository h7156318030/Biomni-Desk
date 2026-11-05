---
title: Pooled CRISPR screen analysis (bulk or single-cell readout)
description: Analyse sgRNA counts from a pooled CRISPR screen (bulk), or the guide-to-transcriptome assignments of Perturb-seq (single-cell), to find genes that affect the phenotype
category: Transcriptomics
when_to_use: The user has sgRNA counts from a CRISPR screen, or single-cell perturbation data, and asks which genes' knockout changes the cells
avoid: Results are unreliable when sgRNA coverage is low; false positives must be corrected with controls; guide assignment in single-cell data needs a purity check
uses: MAGeCK, pandas, scanpy
chain: Upstream is sgRNA design (sgrna-design) or sequencing; downstream goes to target assessment
---
## Steps
1. Bulk screens: take the sgRNA count matrix, normalise by library size (median-ratio method), and calculate the enrichment or depletion of each sgRNA.
2. Gene level: with MAGeCK or a similar method, combine the sgRNAs of the same gene and rank them by RRA.
3. Single-cell (Perturb-seq): assign sgRNAs to each cell (the maximum count), and remove cells with more than one guide. Group the cells by guide, and compare their transcriptomes with the non-targeting controls.
4. Effects: compare each knockout gene with the controls, and find the significant phenotypes.
5. Quality control: sgRNA coverage, the distribution of the controls, and batch effects.

## Quality bar
- Non-targeting controls are required, and they are used to estimate the null hypothesis.
- In single-cell data, filter out cells with multiple guides and cells with no guide.
- The effects of several sgRNAs for the same gene must point in the same direction.

## Output conventions
- Table: gene, ranking score, FDR, effect size, number of sgRNAs that agree.
- State the library, the coverage, the control design, the normalisation method and the date.
