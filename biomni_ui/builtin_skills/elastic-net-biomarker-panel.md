---
title: Elastic-net biomarker panel (with nested cross-validation)
description: Use elastic-net or LASSO logistic regression to select a compact panel of predictive biomarkers, and check it with nested cross-validation and an independent cohort
category: Multi-omics
when_to_use: The user wants a small set of biomarkers, chosen from many features, that predicts a binary outcome such as response or disease
avoid: With few samples and many features the selected panel is very unstable; results without an independent cohort validation are only exploratory; do not tune parameters on the test set
uses: scikit-learn, pandas; stability selection can use your own resampling implementation
chain: Upstream is the standardised feature matrix and outcome labels; downstream is survival-analysis-clinical or independent validation
---
## Steps
1. Data: a feature matrix (samples × features, standardised) and a binary outcome label. Split off a training cohort and an independent validation cohort.
2. Nested cross-validation: evaluate performance with 5-fold outer cross-validation; use LogisticRegressionCV in the inner loop to choose the regularisation strength and the l1 ratio.
3. Stability selection: subsample repeatedly, count how often each feature is selected, and keep the features selected above a threshold (for example 0.8).
4. Final model: fit the selected features on the whole training cohort, and record the coefficients.
5. Independent validation: calculate the AUC and calibration on the independent cohort, without any further tuning.

## Quality bar
- Only the outer-loop metrics of nested cross-validation are a performance estimate; do not report the inner-loop results as performance.
- State the ratio of biomarkers to samples (as a rule of thumb, at least 10 samples per biomarker).
- Compare the distribution of the independent validation cohort with the training cohort; if they differ widely, say so.

## Output conventions
- Table: biomarker, coefficient, selection frequency, outer-loop AUC, independent-cohort AUC.
- State the number of samples, the number of features, the cross-validation scheme, the random seed and the date.
