---
title: Target druggability (Open Targets tractability)
description: Judge which drug modalities (small molecule, antibody, PROTAC, other) suit a human target, and list the number of known drugs and clinical candidates
category: Drug discovery & safety
when_to_use: The user asks whether a target is druggable, whether a small molecule or an antibody suits it, or whether any drugs are known; or the target assessment needs druggability evidence
avoid: Cannot replace structural and experimental validation; the target name must be a human gene symbol, and for a complex or a family name, confirm with the user first; no virtual screening or docking is done here
uses: biomni_ui.dbtools.target_tractability
chain: Upstream is often target assessment or disease association (open-targets); downstream can be tissue expression specificity (tissue-expression-specificity) to judge safety
---
## Steps
1. Get the druggability for a gene symbol:
```python
from biomni_ui.dbtools import target_tractability
print(target_tractability("EGFR"))
```
   The first line of the output gives the number of known drugs and clinical candidates. After that come the evidence labels by modality (small molecule, antibody, PROTAC, other modality).
2. Translate the evidence labels into conclusions by modality:
   - Small molecule: one of "Approved Drug" or "High-Quality Ligand / Pocket" means the target is more likely to be druggable with a small molecule.
   - Antibody: "UniProt loc high conf" or "SigP or TMHMM" (extracellular or membrane protein) means antibodies are likely to reach it.
   - PROTAC: labels such as "Literature" or "Half-life Data" indicate evidence relevant to degradation.
3. If the user asks "which drugs?", add specific compounds with `query_chembl` or `chembl_target_compounds` (see the known active compounds for a target skill).

## Quality bar
- The labels only mean that the evidence allows it; they do not mean that the drug works well or is safe.
- Figures such as "82 known drugs" must carry their source and query date, and must not be presented as market or clinical success rates.
- Align the target name with the gene symbol (confirm with `uniprot_lookup` or `resolve_aliases`); old symbols and aliases can return the wrong entry.
- A high small-molecule label does not mean a small molecule can act selectively on this target. Check tissue expression and homologous proteins (see the related skills).

## Output conventions
- Table: modality, judgement, supporting evidence (the original label), strength of conclusion (strong, moderate, weak).
- State the data source (Open Targets Platform), the query date and the gene symbol of the target.
