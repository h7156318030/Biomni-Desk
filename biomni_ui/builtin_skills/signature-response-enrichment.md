---
title: Therapy response enrichment of a gene signature (GSVA over time)
description: Calculate the activity of a gene signature (GSVA or ssGSEA) in samples before and after treatment, and compare how responders and non-responders change during treatment
category: Transcriptomics
when_to_use: The user asks whether a signature rises after treatment, or whether pathway activity differs between responders and non-responders during treatment; this needs treatment time points and response labels
avoid: With too few samples (fewer than 5 per group) the conclusions are unstable; with too few signature genes (fewer than 10) the activity scores are unstable; whether the signature is causally linked to efficacy needs independent validation
uses: gseapy, pandas, scipy
chain: Upstream is the signature definition (such as consensus-disease-signature or functional-enrichment-from-degs); downstream goes to survival analysis (survival-analysis-clinical)
---
## Steps
1. Prepare: an expression matrix (genes × samples, log scale), the signature gene sets (as a dictionary), and the sample metadata (time point, response label, patient ID).
2. Calculate the signature activity (ssGSEA, giving one score per sample):
```python
import gseapy as gp
ss = gp.ssgsea(data=expr, gene_sets=signature_dict, sample_norm_method="rank", outdir=None)
scores = ss.res2d.pivot(index="Name", columns="Term", values="NES").T
```
3. Change with treatment: for each patient, calculate the paired difference (after treatment minus before treatment), then compare the differences between responders and non-responders (Mann–Whitney).
4. Report the effect size and its confidence interval, not only a p value.

## Quality bar
- A paired design needs a paired test; do not treat the two time points of one patient as independent samples.
- State the source of the signature gene set. Different scoring methods (ssGSEA, GSVA, z-score) give different results, so state which one you used.
- State the definition of the response label (for example RECIST or the efficacy criteria), and freeze it before the analysis.

## Output conventions
- Table: signature name, time point, medians for responders and non-responders, the difference, p value, effect size.
- State the number of samples, the number of patients, the number of signature genes, the method and the response definition.
