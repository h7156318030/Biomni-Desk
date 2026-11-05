---
title: Proteomics differential expression (mass spectrometry)
description: Run a differential analysis on PSM or protein abundance matrices from mass-spectrometry proteomics, using a variance estimate that accounts for peptide counts, with multiple-testing correction
category: Proteomics & cytometry
when_to_use: The user has mass-spectrometry proteomics data and asks which proteins change between two groups
avoid: Proteins with many missing values (for example more than 50%) must be filtered first; the variance estimate is unstable for proteins with few peptides; analysis of modification sites needs a separate workflow
uses: limma, DEqMS; pandas
chain: Upstream is the quantitative mass-spectrometry result (a protein table or PSM table); downstream goes to functional enrichment or network analysis
---
## Steps
1. Preprocessing: filter out proteins with too many missing values, impute the missing values with left-censored or KNN imputation (state the method), and normalise by median.
2. Variance model: account for each protein's peptide count or PSM count, and adjust the variance estimate with a DEqMS-type method.
3. Differential test: compare the groups, and calculate log2FC, the t statistic and the p value.
4. Multiple testing: Benjamini–Hochberg correction.
5. Results: up- and down-regulated proteins, with their peptide counts and missing-value rates.

## Quality bar
- The p values of proteins with few peptides are often too optimistic; use the adjusted variance.
- Report the imputation method; if the proportion imputed is high, be cautious about the conclusions.
- Check the distribution of batches and samples first.

## Output conventions
- Table: protein, gene, log2FC, p value, FDR, peptide count, missing-value rate.
- State the sample numbers, the normalisation and imputation methods, the thresholds and the date.
