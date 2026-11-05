---
title: Multi-omics integration (MOFA+ factor analysis)
description: Integrate two or more omics layers with MOFA+ to find shared and layer-specific latent factors, and explain the features that drive each factor
category: Multi-omics
when_to_use: The user has two or more omics datasets from the same samples (for example transcriptome plus methylation) and asks what varies together across the omics layers
avoid: Samples must correspond across the omics layers (the same sample IDs); state how layers with much missing data were handled; factor interpretation needs biological validation
uses: MOFA2, or mofapy2 in Python; scikit-learn
chain: Upstream is the standardised matrix for each omics layer; downstream goes to bulk-omics-clustering and functional enrichment
---
## Steps
1. Align the samples: align the sample IDs across the omics layers; keep samples that are missing a layer and mark them.
2. Preprocess: standardise each layer separately (centre and scale to similar variance).
3. Train MOFA+: set the number of factors (start with a large number, then trim by the proportion of variance explained).
4. Variance decomposition: the proportion of variance each factor explains in each layer. Distinguish shared factors (present in several omics layers) from layer-specific factors.
5. Interpretation: the high-loading features of each factor, with enrichment analysis; compare with clinical variables.

## Quality bar
- Report the basis for choosing the number of factors (the marginal gain in variance explained).
- When one layer has very little variance, its factors may reflect only noise.
- Correct the associations between factors and clinical variables for multiple testing.

## Output conventions
- Figures: heatmap of variance explained, scatter plot of factors against samples.
- Table: proportion of variance explained by each factor, its high-loading features, enrichment results.
- State the omics types, the number of samples, the number of factors, the standardisation method and the date.
