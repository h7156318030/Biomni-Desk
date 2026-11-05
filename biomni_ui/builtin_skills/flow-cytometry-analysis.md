---
title: Flow cytometry data analysis (FCS files)
description: Process FCS files from flow cytometry, mass cytometry (CyTOF) or spectral flow cytometry: compensation, transformation, gating, clustering and population comparison
category: Proteomics & cytometry
when_to_use: The user has FCS files or exported cell population data, and asks what the proportion of a cell population is, or how the phenotypes of different groups differ
avoid: The compensation matrix must match the instrument; gating needs control samples; results from automatic clustering must be checked by hand
uses: fcsparser, scikit-learn, pandas; FlowSOM or CATALYST are R packages
chain: Upstream is the instrument output; downstream is the statistical comparison of population proportions
---
## Steps
1. Read: load the FCS file with fcsparser, and check the channel names and the fluorescence intensity ranges.
2. Compensation: correct spillover with single-stain controls; check the scatter plots after compensation.
3. Transformation: transform fluorescence data with arcsinh (for CyTOF, usually cofactor 5) or logicle.
4. Gating: first remove debris and dead cells, then gate on the markers; use FMO controls to set the positive thresholds.
5. Clustering (optional): cluster the transformed data (FlowSOM or k-means), and annotate the populations by hand.
6. Comparison: test the population proportions between groups statistically, accounting for repeated measures within samples.

## Quality bar
- A positive threshold without a control is unreliable.
- Automatically clustered populations must be checked against marker genes; do not judge them by their number alone.
- Compare proportions with the sample as the unit of analysis.

## Output conventions
- Figures: a gating diagram, and a UMAP or heatmap of the populations.
- Table: population, proportion, between-group comparison and corrected p value.
- State the channels, the source of the compensation, the transformation parameters and the date.
