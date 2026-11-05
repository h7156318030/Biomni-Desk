---
title: Generative molecule design (target-directed)
description: Use a generative model or fragment assembly to propose candidate molecules around a target's activity, drug-likeness, synthesisability and novelty, then filter them with scores
category: Molecular & protein design
when_to_use: The user wants to design new small molecules for a target, to generate lead compounds, or to perform scaffold hopping
avoid: Generated molecules must pass synthesis-feasibility and structure checks; activity cannot be decided here, only candidates can be proposed; if no trained generative model is available on this computer, say so
uses: rdkit, the binding-affinity model
chain: Upstream is the ChEMBL activity data and the target structure; downstream goes to large-scale-virtual-screening or ADMET checks
---
## Steps
1. Define the target: the target protein, the required activity range, and property constraints (molecular weight below 500, logP below 5, a synthesisability score).
2. Generate: make variants of known active molecules by scaffold hopping or fragment assembly; if a generative model is available, sample from it following its workflow.
3. Filter: remove invalid structures, duplicates and PAINS motifs; filter for drug-likeness with Lipinski and QED.
4. Score: predict activity with the activity model, and filter with a synthetic accessibility (SA) score.
5. Novelty: the maximum similarity to the training set; only compounds below 0.5 count as novel.
6. Before output, compare the candidates with known compounds and check that they do not copy an existing patented compound.

## Quality bar
- Activity predictions are unreliable outside the chemistry of the training set; flag this.
- The synthetic feasibility of generated molecules must be checked by a person; the SA score is only a guide.
- Do not generate known dangerous compounds or controlled substances. When such a request comes up, refuse and explain why.

## Output conventions
- Table: molecule SMILES, predicted activity, QED, SA score, maximum similarity to the training set.
- State the generation method, the filter rules, the model version and a note that experimental validation is needed.
