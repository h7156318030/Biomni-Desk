---
title: Small-molecule binding affinity model (honest benchmark)
description: Train a target-specific affinity model from ChEMBL IC50, Ki or Kd data, evaluate it on a scaffold-split benchmark, then screen compounds with it
category: Molecular & protein design
when_to_use: The user wants an activity prediction model for a target, or wants to rank compounds in a library by predicted activity
avoid: Random splits badly overestimate performance; data from different experimental sources must be stated; a predicted activity is not a measured one; predictions far outside the training chemistry are unreliable
uses: dbtools.chembl_target_compounds, rdkit, scikit-learn; chemprop optionally
chain: Upstream is the data curation in chembl-hit-series-sar-docking; downstream goes to large-scale-virtual-screening or generative-molecule-design
---
## Steps
1. Get the data: pIC50 or pKi values from ChEMBL (unified as pChEMBL values), de-duplicated; where one compound has several values, use the median.
2. Scaffold split (Bemis–Murcko): the training and test sets share no scaffolds.
3. Features: Morgan fingerprints plus descriptors. Model: a random forest as the baseline, then try chemprop.
4. Evaluation: R², RMSE and Spearman correlation on the test set; compare with simple baselines, such as predicting from molecular weight.
5. Application: predict for candidate compounds, and give the nearest-neighbour similarity to the training set. Mark predictions with low similarity as unreliable.

## Quality bar
- Always report the baseline model, to show that the new model improves on it.
- Do not model with fewer than about 100 training compounds.
- Do not tune parameters repeatedly on the test set.

## Output conventions
- Table: model, features, cross-validation and test-set metrics, baseline metrics, applicability domain.
- State the data version, the number of compounds, the split method and the date.
