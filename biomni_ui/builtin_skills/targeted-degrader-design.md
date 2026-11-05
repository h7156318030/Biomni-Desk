---
title: Targeted protein degrader (PROTAC) design and initial screen
description: Design heterobifunctional degraders for a protein: choose an E3 ligase (CRBN or VHL), a ligand exit vector and a linker, and check drug-likeness and assembly
category: Molecular & protein design
when_to_use: The user wants to design a PROTAC or molecular-glue degrader, or asks whether a target can be degraded or how to choose the linker
avoid: Degradation efficiency needs validation in cell experiments; computation can only screen assembly and physicochemical properties; the ternary complex of E3 and target cannot be judged from docking alone
uses: rdkit, dbtools.chembl_target_compounds, dbtools.uniprot_lookup
chain: Upstream is target druggability (target-tractability-druggability); downstream goes to ADME and safety checks
---
## Steps
1. Target ligand: take the inhibitors of the target from ChEMBL, and choose one with a clear structure and good activity as the warhead.
2. Exit vector: find a position on the ligand that does not disturb binding (judged from the SAR or a co-crystal structure).
3. E3 ligand: a CRBN ligand (such as a thalidomide analogue) or a VHL ligand, chosen according to the target. Give the reason for the choice.
4. Linker: enumerate several lengths of PEG or alkyl chains (for example 8 to 16 heavy atoms), and assemble them with the two ligands.
5. Checks: molecular weight (usually below 1200), the number of hydrogen-bond donors and acceptors, and solubility; flag risks beyond the bRo5 (beyond rule of five) space.

## Quality bar
- The linker length needs a design basis; do not simply enumerate.
- Verify the structures of the assembled molecules with rdkit, and avoid chemically implausible bonds.
- Degradation must be confirmed by experiments inside cells; computational results are candidates only.

## Output conventions
- Table: candidate structure, E3 type, linker, molecular weight, physicochemical properties.
- State the warhead source, the reason for the E3 choice, and the experiments still needed.
