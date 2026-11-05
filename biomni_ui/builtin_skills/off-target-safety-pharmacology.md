---
title: Small-molecule off-target and safety pharmacology risk (safety target panel)
description: For a given small molecule, check the safety-related targets it might act on (such as hERG, CYP enzymes, 5-HT2B and transporters), and summarise calculated predictions with known data
category: Drug discovery & safety
when_to_use: The user asks whether this compound carries a cardiotoxicity risk, or whether it inhibits CYP enzymes, or wants an early safety screen
avoid: Computational predictions cannot replace experiments (such as a hERG patch-clamp assay); results give only risk flags, not clinical safety conclusions; confirm the structure of a compound from its name first
uses: rdkit, dbtools.chembl_target_compounds, prediction models
chain: Upstream is molecular-property-admet and ChEMBL data; downstream goes to adme-ml-modeling to train a dedicated model
---
## Steps
1. Confirm the compound structure (SMILES) and standardise it.
2. Look up known activity: for the safety targets (KCNH2, which is hERG; CYP3A4; HTR2B; SLC transporters and so on), use ChEMBL to find data for this compound or close analogues.
3. Structural alerts: flag PAINS and toxicity alerts with rdkit (such as nitro groups and epoxides), and explain what they mean without making a diagnosis.
4. If a dedicated prediction model is available, give a probability following the adme-ml-modeling workflow, and label its applicability domain.

## Quality bar
- If the compounds with known data differ in structure from the target compound, use them only as references.
- Structural alerts only indicate that something needs attention; they do not establish toxicity.
- Without experimental data, the conclusion can only be "risk to be verified".

## Output conventions
- Table: safety target, known activity or predicted value, source, risk grade (flag, needs attention, higher risk).
- State the data sources, the model version, and the recommendation that experimental validation is needed.
