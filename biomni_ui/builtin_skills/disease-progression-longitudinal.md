---
title: Disease progression trajectories from longitudinal multi-omics
description: From repeated omics measurements on the same patients, reconstruct disease progression trajectories, time-dependent states and patient heterogeneity
category: Multi-omics
when_to_use: The user has omics or clinical measurements from the same patients at several time points, and asks how the disease develops or whether patients fall into groups with different progression patterns
avoid: With fewer than three time points the trajectories are unreliable; state how missing time points were handled; a trajectory is a model-based inference and should be validated against clinical outcomes
uses: pandas, scikit-learn, mixed-effects models
chain: Upstream is the standardised omics data at each time point; downstream is survival-analysis-clinical, to check the relationship between progression patterns and outcomes
---
## Steps
1. Organise the panel data: patient ID, time point and measurement (as a wide or long table of features).
2. Within-patient change: for each feature, fit a mixed-effects model (random intercept and slope) to get each patient's rate of change.
3. Dimension reduction: apply PCA or UMAP to the individual rates of change to find patterns of change.
4. Progression states: cluster the patterns of change; each cluster represents one progression trajectory. Order the patients by trajectory.
5. Validation: association of the different trajectories with clinical outcomes (such as survival or disease severity).

## Quality bar
- Check the residuals and convergence of the mixed-effects models.
- Do not impute missing time points simply; use a model that handles missing data.
- Choose the number of trajectory clusters with a stability test.

## Output conventions
- Figures: individual trajectory plot, clustering plot of progression patterns.
- Table: number of patients per progression pattern, representative features, association with outcomes.
- State the number of time points, how missing data were handled, the model and the date.
