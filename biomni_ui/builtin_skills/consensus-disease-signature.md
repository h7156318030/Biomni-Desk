---
title: Cross-cohort consistent disease expression signature (random-effects meta-analysis)
description: Run a differential analysis on each of several independent bulk expression cohorts, then combine them with a random-effects model to get a gene signature that is consistent across cohorts
category: Transcriptomics
when_to_use: The user has several expression cohorts of a disease versus control and asks which genes change in all of them, or wants a reusable disease signature
avoid: If the cohorts differ too much in platform, tissue or group definitions, combining them will mislead, so say so first; this workflow cannot be used with a single cohort
uses: pandas, numpy, scipy
chain: Upstream is the differential analysis of each cohort (DESeq2 or limma can be used); downstream can be drug-repurposing-indication-expansion for the reversal analysis
---
## Steps
1. For each cohort, run a disease versus control differential analysis on its own, and get each gene's effect size (log fold change) and standard error.
2. Random-effects pooling (DerSimonian–Laird):
```python
import numpy as np
def dersimonian_laird(effects, ses):
    w = 1 / np.square(ses)
    fixed = np.sum(w * effects) / np.sum(w)
    q = np.sum(w * np.square(effects - fixed))
    k = len(effects)
    tau2 = max(0.0, (q - (k - 1)) / (np.sum(w) - np.sum(w**2) / np.sum(w)))
    w_re = 1 / (np.square(ses) + tau2)
    mu = np.sum(w_re * effects) / np.sum(w_re)
    se = np.sqrt(1 / np.sum(w_re))
    return mu, se, tau2, q
```
3. For each gene, calculate the z value and p value, and correct for multiple testing (Benjamini–Hochberg).
4. Direction consistency: require that all (or nearly all) cohorts have effects with the same sign before a gene enters the consistent signature.

## Quality bar
- Flag genes with high heterogeneity (I², Q) separately; do not treat them as consistent.
- When sample sizes are very unbalanced, a large cohort dominates the effect size; report the sample size of each cohort.
- Correct each cohort for batch effects first, and check each cohort's distribution by eye before combining.

## Output conventions
- Table: gene, pooled log fold change, 95% confidence interval, p value, FDR, heterogeneity I², number of cohorts with a consistent direction.
- State the cohorts included (GEO accessions), the platforms, the sample sizes and the analysis date.
