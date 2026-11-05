---
title: Population pharmacokinetic and pharmacodynamic models (PK/PD)
description: Fit a population pharmacokinetic model (compartments, clearance, covariates) to concentration-time data, check it with a visual predictive check (VPC), and add a pharmacodynamic endpoint when needed
category: Drug discovery & safety
when_to_use: The user has drug concentration data (several time points per subject) and asks what the clearance is, how body weight or kidney function affects exposure, or whether a dosing regimen is appropriate
avoid: With too few data points (fewer than 3 time points per individual) the model is unreliable; this is model fitting and does not replace clinical pharmacology judgement; the results cannot be used directly to set doses
uses: NONMEM and nlmixr2 are not available on this computer; scipy in Python can fit a one-compartment model as a basis; a formal population model needs nlmixr2 in R
chain: Upstream is the clinical or animal concentration data; downstream goes to clinical-trial-design-simulation to design the dosing regimen
---
## Steps
1. Organise the data: subject ID, time (hours), concentration, dose and dosing times, and covariates (body weight, age, kidney function).
2. Base model (one compartment, intravenous): C(t) = (Dose/V)·exp(−CL/V·t). Estimate CL and V by nonlinear least squares (between-subject variability as log-normal random effects; for the formal fit, use nlmixr2).
3. Covariates: check the relationship of CL with body weight and kidney function (for example log-linear), and keep the significant ones.
4. Model check: a visual predictive check (VPC). Simulate 1000 times and check whether the observations fall within the prediction intervals.
5. Dosing simulation: use the fitted parameters to simulate different doses, and check whether the trough concentration or the area under the curve falls within the target range.

## Quality bar
- With too few subjects or concentration points, the parameter confidence intervals will be wide; report this.
- A failed VPC means the model is wrong; do not judge it by the p values of the parameters alone.
- Simulation results are for discussion only, not dosing advice.

## Output conventions
- Table: parameters (CL, V, covariate effects), confidence intervals, VPC results.
- State the amount of data, the model structure, the software and its version.
