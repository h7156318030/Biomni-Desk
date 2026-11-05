---
title: Small-molecule physicochemical properties and drug-likeness
description: Calculate molecular weight, logP, hydrogen bonding, TPSA and QED from SMILES with RDKit, and flag them against the Lipinski, Veber and PAINS rules
category: Drug discovery & safety
when_to_use: The user gives one or a batch of small molecules (as SMILES or drug names) and wants to assess drug-likeness or physicochemical properties, or to do an initial screen
avoid: For a real ADMET prediction (solubility, permeability, hERG, metabolic stability and so on), this skill is not enough: it gives rule-of-thumb filters, not a predictive model, and this must be said; the rules do not apply to large molecules, peptides or PROTACs
uses: biomni_ui.analysis.molecule_properties, biomni_ui.dbtools.chembl_target_compounds
chain: Upstream is often the ChEMBL target compound search; for drug names, look up the SMILES first (PubChem)
---
## Steps
1. Get the SMILES: the user gives them directly; if only a drug name is given, look it up in PubChem (`query_pubchem(prompt="SMILES of imatinib")`), and write out the SMILES and CID so that they can be checked.
2. Run:
```python
from biomni_ui.analysis import molecule_properties
print(molecule_properties(["CC(=O)Oc1ccccc1C(=O)O", "CN1CCC[C@H]1c1cccnc1"], out="molecules"))
```
3. Read the table: MW, logP, HBD, HBA, TPSA, RotB, QED, the number of Lipinski violations, whether Veber passes, and PAINS alerts. Invalid SMILES are marked; tell the user about them.
4. For a batch of compounds, give a screening conclusion: how many have zero violations, which have PAINS alerts, which fall outside the range, and why.

## Quality bar
- The Lipinski "rule of five" was written for oral small molecules. **Natural products, antibiotics and targeted protein degraders often violate it legitimately**, so do not eliminate compounds on that basis alone.
- PAINS are a warning of possibly false-positive structures, not proof of inactivity.
- Do not report solubility, toxicity, half-life or other values that this function does not calculate.

## Output conventions
- Start with the conclusion (how many molecules, how many pass), then the table, then the statement "These are rule-of-thumb filters, not ADMET predictions."
- File: `molecules.csv`.
