---
title: Two-sample Mendelian randomisation (causal inference)
description: Use genetic instrumental variables to estimate the causal effect of an exposure on an outcome from two independent GWAS (exposure and outcome), with sensitivity analyses
category: Genomics & genetics
when_to_use: The user asks whether a factor causes a disease, or the causal effect of a protein level, and has suitable GWAS summary statistics
avoid: Instrumental variables must satisfy the assumptions of relevance, independence and exclusion; if an assumption fails, the conclusion is invalid; overlapping samples cause bias; this does not replace a randomised controlled trial
uses: TwoSampleMR, or a Python MR implementation; the GWAS data must be downloaded
chain: Upstream is the GWAS for the exposure and the outcome; downstream goes to gwas-to-function-twas for mechanistic follow-up
---
## Steps
1. Choose instrumental variables: independent variants in the exposure GWAS that reach genome-wide significance (p < 5×10⁻⁸), after LD pruning (r² < 0.001).
2. Extract the outcome effects: the beta and standard error of the same variants in the outcome GWAS, with the allele direction harmonised.
3. Main analysis: inverse-variance weighted (IVW). Exclude weak instruments (F statistic below 10).
4. Sensitivity analyses: MR-Egger (to check pleiotropy), weighted median, and leave-one-out.
5. Report the effect, its confidence interval and significance, and state the assumptions of each analysis.

## Quality bar
- Report the F statistic of the instruments; F below 10 indicates weak-instrument bias.
- If the pleiotropy test (the MR-Egger intercept) is significant, downgrade the conclusion.
- Overlap between the two GWAS samples biases the estimate; say so.

## Output conventions
- Table: method, number of instruments, effect, confidence interval, p value, F statistic, pleiotropy test.
- State the GWAS sources and sample sizes, the instrument selection criteria, the software versions and the date.
