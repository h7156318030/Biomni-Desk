---
title: Clinical survival analysis (KM, log-rank, Cox)
description: Kaplan–Meier curves, the log-rank test and Cox proportional hazards regression for a clinical table with follow-up time, an event indicator, and groups or covariates
category: Clinical & statistics
when_to_use: The user has a table with follow-up time, whether an event occurred (death, relapse and so on), and groups or covariates, and wants to compare survival or estimate a hazard ratio
avoid: If there is no censoring information and the outcome is only binary, use a proportion test or logistic regression; if follow-up times are date strings, convert them to numbers first; with very few samples or events, describe the data and draw no conclusions
uses: biomni_ui.analysis.survival_km_cox
chain: Upstream may be clinical data from cBioPortal or GEO; downstream can be a report with charts
---
## Input
A CSV or TSV file with: `time` (a number; confirm the unit with the user, or infer it from the column name), `event` (1 = event occurred, 0 = censored), and optional group and covariate columns.

## Steps
1. Look at the data: the number of rows, the number of events, missing values, and the size of each group. **If there are fewer than about 10 events, only describe the data and state clearly that the power is insufficient.**
2. Run:
```python
from biomni_ui.analysis import survival_km_cox
print(survival_km_cox("clinical.csv", time="OS_months", event="OS_event", group="risk", covariates=["age", "stage"], out="os"))
```
3. Read the output: the n and the number of events in each group, the median survival, the log-rank P for two groups, and the Cox hazard ratio HR [95% CI] with its P.
4. If the groups come from a continuous variable (such as gene expression), state how the cut-point was chosen. **Choosing the best cut-point from the data itself inflates significance**; either use the median, or state clearly that the analysis is exploratory.

## Quality bar
- `event` must be 0 or 1; the function rejects other values.
- Proportional hazards assumption: if the KM curves clearly cross, warn that the log-rank test and the Cox model may not apply.
- Multiple comparisons: when many genes or groups are tested at once, correct for it and state the correction.

## Output conventions
- A conclusion sentence: which group survives better, the HR with its interval, the p value, and the number of samples and events.
- Files: `os_km.png` and `os_cox.csv`.
- Limitations: length of follow-up, proportion censored, and whether confounders were adjusted for.

## Do not
- Do not describe a small p value as a large effect; do not report a precise HR and draw strong conclusions when there are very few events.
