---
title: Polygenic risk score (PGS Catalog)
description: Get trait weights from the PGS Catalog, calculate polygenic risk scores for individuals' genotypes, and align alleles and compare populations
category: Genomics & genetics
when_to_use: The user asks for the polygenic risk score of a trait, or wants to compare PRS across populations, and has genotype data
avoid: The predictive power of a PRS drops with ancestry, so interpretation across ancestries must be cautious; a PRS cannot be used for a clinical diagnosis of an individual; the weights' alleles must be harmonised with the data
uses: download the scoring file from the PGS Catalog; pandas
chain: Upstream is the genotype data; downstream goes to interpretation of population structure or disease risk
---
## Steps
1. Get the scoring file: download the weights by trait ID (the PGS identifier), and record the number of variants, the source and the build version.
2. Allele harmonisation: align the weights' effect alleles with the individual data, and flip or drop ambiguous sites (A/T, C/G).
3. Calculation: for each individual, PRS = the sum of (effect allele count × weight), then standardise against a reference population.
4. Comparison: show the distributions of different ancestries separately, and standardise them against the same reference.

## Quality bar
- The reference build of the genotype data (for example GRCh38) must match the weights.
- Report the proportion of missing variants; if too many are missing, the result is not credible.
- The predictive power of a PRS (AUC, R²) must be validated in the target population.

## Output conventions
- Table: PRS distribution for individuals or groups, standardised values, proportion of variants covered.
- State the score ID, the version, the reference population, the missing rate and the date.
