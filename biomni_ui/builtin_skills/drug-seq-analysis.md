---
title: Differential expression for drug screening (DRUG-seq and similar)
description: Run a dose-by-dose differential expression analysis of bulk transcriptomes after compound treatment, using the vehicle control as baseline, and use vehicle-versus-vehicle null comparisons to control false positives
category: Transcriptomics
when_to_use: The user has expression data from compound-treated samples (DRUG-seq, plate-based bulk RNA-seq) and asks which compounds or doses changed which genes
avoid: Cannot be done without vehicle controls; comparisons between several compounds must state the batch; this does not judge the drug's efficacy
uses: pydeseq2, pandas
chain: Upstream is the count matrix and the sample design table; downstream goes to signature-reversal-lincs for the compound reversal analysis
---
## Steps
1. Organise the sample table: for each well, the compound, the dose, the plate number and a control marker. Label the vehicle control as the baseline.
2. For each compound and dose, run a differential expression analysis against the vehicle controls on the same plate (pydeseq2 or an equivalent limma workflow), with the plate number as a covariate:
```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
dds = DeseqDataSet(counts=counts.T, metadata=meta, design_factors=["plate", "condition"])
dds.deseq2()
stats = DeseqStats(dds, contrast=["condition", "compound_X_10uM", "vehicle"])
stats.summary()
res = stats.results_df
```
3. Null comparison: randomly split the vehicle wells into two "pseudo-treatment" groups, run the same differential analysis, and count the false positives (this should be close to zero).
4. Summarise the results for one compound across doses by consistency (direction and ranking), rather than by looking only at the significant genes at a single dose.

## Quality bar
- With fewer than three vehicle wells per plate, the statistical power is low and the conclusions must be downgraded.
- If the null comparison gives many false positives, plate or well-position effects have not been corrected; fix them first.
- State the significance threshold (FDR < 0.05 and |log2FC| > 1) in the answer.

## Output conventions
- Table: compound, dose, numbers of significantly up- and down-regulated genes, false positives from the null comparison.
- State the number of samples, the number of plates, the control design, the software versions and the thresholds.
