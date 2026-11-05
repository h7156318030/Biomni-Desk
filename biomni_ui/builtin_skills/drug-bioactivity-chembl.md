---
title: Known active compounds for a target (ChEMBL)
description: Retrieve the strongest measured compounds for a target in ChEMBL (IC50, Ki and similar), and calculate their drug-like properties
category: Drug discovery & safety
when_to_use: The user asks which known inhibitors or active compounds exist for a target, what the strongest one is, or what the activity data look like; or which target and indication a compound has
avoid: Retraining a structure-activity model or running virtual screening is not possible here (this computer has no docking software), so say so; when a target has no human single-protein entry (for example a complex), the function lists candidates, and you should confirm with the user which one they want
uses: biomni_ui.dbtools.chembl_target_compounds, biomni_ui.analysis.molecule_properties, query_chembl
chain: Upstream is often target assessment; downstream can be molecular properties and a report with charts
---
## Steps
1. Retrieve the active compounds:
```python
from biomni_ui.dbtools import chembl_target_compounds
print(chembl_target_compounds("EGFR", max_results=15, standard_type="IC50"))
```
   The output lists: compound (ChEMBL ID) | activity value (nM) | assay type (B = binding, F = functional) | SMILES.
2. If you need properties, pass the SMILES from the output to `molecule_properties` (see the small-molecule physicochemical properties and drug-likeness skill).
3. For the mechanism and indications of one compound, use `query_chembl(prompt="mechanism and indications of CHEMBL941")` (the natural-language tool is available).

## Quality bar
- **A compound often has many measurements, and this function keeps only the strongest one for each**, which is optimistic. When you need the range, use the natural-language tool to get all the measurements.
- Values below 0.01 nM have been filtered out, as they are usually unit errors in the raw data; tell the user this.
- IC50 values from different cells or enzymes, or from different laboratories, cannot be compared directly; report binding (B) and functional (F) assays separately.
- Mutant targets (such as EGFR T790M) are often separate ChEMBL entries; confirm which one the user wants.

## Output conventions
- Table: compound, value, assay type, ChEMBL link (`https://www.ebi.ac.uk/chembl/compound_report_card/<ID>/`).
- State the filtering rules (exact values, de-duplication, filtering) and the data date.
