---
title: Evidence synthesis (meta-analysis)
description: Combine the effect sizes and standard errors of several studies into a fixed or random effects result, with a forest plot and heterogeneity statistics
category: Literature & evidence
when_to_use: The user already has the effect size (mean difference, log odds ratio, log risk ratio or hazard ratio) and standard error from several studies, and wants a pooled effect
avoid: The data have not yet been extracted study by study (first run a literature search and extract the values from the full text; do not guess from abstracts); study designs differ too much; with only two studies and very high heterogeneity, do not pool them by force
uses: biomni_ui.analysis.meta_analysis, biomni_ui.lit.paper_abstracts
chain: Upstream is literature search and extraction; downstream can be a report with charts
---
## Input table
A CSV with one row per study: `study` (name), `effect`, `se`. For ratio measures (OR, RR, HR), take the natural logarithm first and set `ratio_scale=True`; the SE is on the log scale too.

## Steps
1. When you extract data, record the source (PMID, DOI or table location). **Numbers must come from the original paper. If a value cannot be found, leave it blank and say so; do not estimate it.**
2. Run:
```python
from biomni_ui.analysis import meta_analysis
print(meta_analysis("studies.csv", effect="log_hr", se="se_log_hr", label="study", out="meta", ratio_scale=True))
```
3. Read the output: the fixed effect, the random effect (DerSimonian–Laird) with its 95% CI, the Q test, I² and τ².
4. When I² is above 50%, base the conclusion on the random-effects result, and explore the sources of heterogeneity (population, dose, design). Do not report only the pooled value.

## Quality bar
- With fewer than five studies, the τ² estimate is unstable and the I² interval is very wide; say so.
- Publication bias has not been assessed (this function has no funnel plot or Egger test); state it as a limitation.
- Do not pool observational studies with randomised trials without saying so.

## Output conventions
- Conclusion: the pooled effect (transformed back to the original scale) with its interval, the p value, the number of studies and I².
- File: `meta_forest.png`.
- A table of data sources (the PMID or DOI of each study).
