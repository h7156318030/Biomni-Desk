---
title: Real-world evidence cohort study (EHR or claims data)
description: Run a cohort study on structured EHR or claims data: build the cohort from diagnosis codes, Table 1, treatment patterns, Kaplan–Meier curves and Cox models
category: Data & workflows
when_to_use: The user has structured real-world data and asks about the survival or efficacy of a treatment, or wants to compare the characteristics of two groups of patients
avoid: Real-world data are affected by confounding and selection bias, so results can only be stated as associations; not possible without data; must not be used for individual treatment decisions
uses: lifelines, pandas, statsmodels
chain: Upstream is data extraction and definition; downstream is the refined analysis in survival-analysis-clinical
---
## Steps
1. Cohort definition: build the cohort with diagnosis codes and inclusion and exclusion criteria, and record the number of patients at each step.
2. Baseline table (Table 1): age, sex, comorbidities. For continuous variables, use the median and interquartile range; compare groups with suitable tests.
3. Treatment patterns: the start and stop dates of treatment, switches and interruptions.
4. Survival: Kaplan–Meier curves and the log-rank test. The start point must be the same for everyone (for example the diagnosis date or the start-of-treatment date).
5. Multivariable: a Cox model adjusted for confounders. Check the proportional-hazards assumption and the number of events (at least 10 events per variable).

## Quality bar
- Freeze the definitions of the start and end points before the analysis.
- Report how missing data were handled.
- Where confounding adjustment is incomplete, state the residual bias.

## Output conventions
- Figures: Kaplan–Meier curves, forest plot.
- Tables: baseline table, Cox results (hazard ratios and confidence intervals).
- State the data source, the number of patients included, the definitions, the model and the date.
