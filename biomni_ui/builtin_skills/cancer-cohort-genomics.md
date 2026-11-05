---
title: Somatic variant frequencies in cancer cohorts (cBioPortal, TCGA)
description: Count the mutation, amplification and deletion frequencies of a gene across cancer types or cohorts, and compare co-alterations across cancer types and cohorts
category: Genomics & genetics
when_to_use: The user asks in which cancers a gene is often mutated, or which mutations co-occur in one cancer type, and wants frequencies or a comparison
avoid: Cohorts differ in inclusion criteria and sequencing methods, so their frequencies cannot be compared directly; statistics for rare events need confidence intervals; do not make clinical judgements about individuals
uses: dbtools.query_cbioportal, pandas
chain: Upstream is a gene list; downstream goes to clinical-variant-allelic-series or target selection
---
## Steps
1. Choose the gene and the cancer types: use query_cbioportal to get the mutations and copy-number changes for the gene in each cohort.
2. Denominator: the number of samples in each cohort. Calculate the frequency and its 95% Wilson confidence interval.
3. Comparison: compare cancer types with Fisher's exact test, with multiple-testing correction.
4. Co-mutation: co-occurrence of two genes in the same cohort, tested with a hypergeometric or Fisher test; report the odds ratio.
5. Report the cohort names, sample numbers, inclusion criteria and the data date.

## Quality bar
- The same patient can be counted in several cohorts; state the de-duplication rule.
- Keep copy-number changes and mutations as separate counts.
- Frequencies in cohorts with fewer than 30 samples are unstable.

## Output conventions
- Table: cancer type, cohort, number of samples, mutation frequency with 95% CI, amplification or deletion frequency.
- State the cBioPortal version, the list of cohorts and the query date.
