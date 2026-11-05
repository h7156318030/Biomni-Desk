---
title: Sample and feature clustering for bulk omics
description: Cluster samples or features in a transcriptome, proteome or metabolome matrix to find data-driven groups, and test how stable the groups are
category: Multi-omics
when_to_use: The user asks how the samples can be grouped, or which features show similar patterns, and the input is a samples-by-features omics matrix
avoid: Batch effects can dominate the clustering and must be checked first; the number of clusters should not be chosen by eye alone; a group is not a biological subtype until it has been validated functionally
uses: scikit-learn, scipy, pandas
chain: Upstream is the standardised matrix; downstream goes to differential analysis or multi-omics-integration
---
## Steps
1. Preprocessing: log-transform, remove low-expression or low-variance features, and centre the features. Check whether the principal components correlate with batch or technical variables.
2. Feature selection: take the top 1000–2000 features by variance.
3. Clustering: hierarchical clustering (Ward) or k-means. Choose the number of clusters with silhouette scores and consensus clustering (repeated subsampling).
4. Stability: subsample 80% of the samples 100 times and compute how often each pair of samples lands in the same cluster (the consensus matrix). Samples with low stability are flagged as borderline.
5. Interpretation: the marker features of each cluster (differences against the other clusters), and comparison with clinical variables.

## Quality bar
- If batch effects are not corrected, the clusters may reflect batch alone.
- The choice of the number of clusters must be justified (silhouette scores, stability).
- With fewer than 20 samples the clustering is unstable; say so.

## Output conventions
- Figures: principal component plot and consensus matrix heatmap.
- Table: samples per cluster, marker features, association with clinical variables.
- State the preprocessing, the number of features, the clustering method, the basis for choosing the number of clusters, and the date.
