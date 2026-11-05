---
title: Computational method iteration with local Biomni (no external API)
description: Without an external API or a GPU, iterate on a computational method using local benchmarks and checkpoints; the focus is on preventing overfitting and keeping a reproducible record
category: Data & workflows
when_to_use: The user wants to iterate on a computational method, but has no external API key, or the data and compute are local
avoid: Local compute is limited, so run large searches in batches; do not tune parameters on the test set; results need an independent validation
uses: pandas, numpy, scikit-learn and the local benchmark scripts; checkpoints are saved as standard files
chain: Choose one of this and tusoai; the output can feed any analysis skill
---
## Steps
1. Benchmark: a fixed data split (training, validation, test). The test set is used only once, at the end.
2. Iterate: for each round, record the parameters, the validation metrics and the code version.
3. Checkpoints: save the results and the random seed at the end of each round, so that the run can be reproduced.
4. Overfitting check: compare the gap between validation and test performance; when the gap is large, stop tuning.
5. Final: evaluate once on the test set, and report the uncertainty.

## Quality bar
- The test set must not be used to choose the method.
- Fix the random seed and report it.
- Report the variance across repeated runs.

## Output conventions
- Table: round, parameters, validation metrics, checkpoint location.
- State the data split, the seed, the code version and the date.
