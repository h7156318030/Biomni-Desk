---
title: Series analysis and structure-activity relationships (SAR) of known active compounds
description: Rank the ChEMBL hit compounds for a target by potency and efficiency, cluster them into chemical series, run maximum common substructure and R-group analysis within each series, then dock representative molecules
category: Drug discovery & safety
when_to_use: The user asks how the known compounds for a target group into series, or which substituent in a series affects activity, and wants a structural explanation
avoid: Assay conditions differ across ChEMBL records and can confuse the SAR, so unify them first; docking is only a supporting aid; compounds without activity data do not take part in the SAR
uses: dbtools.chembl_target_compounds, rdkit, scikit-learn
chain: Upstream is drug-bioactivity-chembl; downstream goes to large-scale-virtual-screening or ligand-binding-mode-analysis
---
## Steps
1. Get the hit compounds (IC50 or Ki, with the unit unified to nM):
```python
from biomni_ui.dbtools import chembl_target_compounds
hits = chembl_target_compounds("EGFR", max_results=200, standard_type="IC50")
```
2. Calculate efficiency metrics (for example the ratio of pIC50 to heavy-atom count, which is LE), and rank by potency and efficiency.
3. Clustering: Morgan fingerprints with Butina or hierarchical clustering (Tanimoto threshold 0.6). Each cluster is one series.
4. SAR within a series: use the maximum common substructure (MCS) to find the core, list the R groups and their activities, and see which substituents raise or lower activity.
5. Representative docking (optional): pick one or two representatives per series, dock them following the large-scale-virtual-screening workflow, and treat the results as reference only.

## Quality bar
- Do not rank together compounds measured in different assay types (binding and functional).
- With fewer than 5 compounds in a series, downgrade the R-group conclusions.
- Check the relationship between docking scores and activity on known compounds; if it fails the check, do not use docking to explain the SAR.

## Output conventions
- Table: series, representative compound, activity range, core structure, key substituents and their effect on activity.
- State the data source (ChEMBL version), the assay conditions, the clustering threshold and the date.
