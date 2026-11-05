---
title: Perturbation response prediction with virtual cell models (CRISPR perturbations)
description: Predict single-cell transcriptome responses to gene perturbations with virtual cell models (such as scGPT or GEARS), and benchmark the predictions against Perturb-seq data
category: Transcriptomics
when_to_use: The user asks how the transcriptome would change after knocking out a gene, or wants to assess how well a virtual cell model predicts
avoid: The prediction models need a GPU and pretrained weights (usually not supported on this computer); predictions only cover perturbations seen in training; results must be benchmarked against experimental data
uses: needs models such as GEARS or scGPT; the Perturb-seq benchmark data must be downloaded
chain: Upstream is the perturbation experiment design (sgrna-design); downstream goes to pooled-crispr-screens for comparison
---
## Steps
1. Benchmark data: a Perturb-seq dataset, grouped by perturbation, with some perturbations held out as the test set.
2. Model: train on the training perturbations, or use a pretrained model, to predict the expression changes for the test perturbations.
3. Evaluation: the correlation between predicted and measured changes (at gene level and at pseudobulk level), compared with a "mean perturbation" baseline.
4. Prediction: for a new perturbation, give the predicted differential genes and pathways.

## Quality bar
- You must compare against a baseline to show that the model does better than a simple average.
- Test perturbations must not have appeared in training.
- Predictions are hypotheses only and cannot replace experiments.

## Output conventions
- Figures: scatter plot of predicted against measured changes, and the baseline comparison.
- Table: test perturbations, correlation coefficients, ranking accuracy.
- State the model version, the dataset, the hold-out scheme and the date.
