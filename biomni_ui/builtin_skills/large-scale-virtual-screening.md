---
title: Large-scale virtual screening (structure-based docking)
description: Dock a compound library against a protein structure, including receptor and ligand preparation, re-docking of the native ligand for validation, scoring and ranking, and scaffold clustering
category: Drug discovery & safety
when_to_use: The user has a protein structure (a PDB entry, or a structure that can be predicted) and a compound library, and wants to find molecules that may bind
avoid: A docking score does not directly measure binding strength; if AutoDock Vina is not installed on this computer, install it first or use a cloud service instead; choosing the wrong receptor conformation leads directly to wrong results
uses: pyscreener, meeko, pdbfixer with openmm, rdkit
chain: Upstream is the target structure (protein-structure-prediction or PDB) and the compound library; downstream goes to scaffold-and-ring-systems-analysis and SAR analysis
---
## Steps
1. Receptor preparation: take the PDB structure, remove water and irrelevant ligands, add hydrogens and repair missing residues (pdbfixer). Keep one native ligand for validation.
2. Re-dock the native ligand: if the RMSD of the re-docked pose is greater than 2 Å, the docking setup is wrong; adjust the box and the parameters first.
3. Compound library: standardise the structures, generate 3D conformers, and prepare PDBQT files (meeko).
4. Docking and scoring: score the whole library with a Vina-type tool, keep the top N, cluster them by scaffold, and choose a representative for each cluster.
5. Visually inspect the representatives (binding pocket, hydrogen bonds) before recommending them.

## Quality bar
- If the docking scores correlate poorly with activity, state that docking is only a preliminary screen.
- Run known active compounds through the same docking as a positive control.
- Large libraries must be processed in batches, and the number of failures in each batch must be recorded.

## Output conventions
- Table: compound, score, scaffold class, key interactions, whether it passed the native-ligand validation.
- State the receptor structure (PDB identifier), the box coordinates, the software versions and the parameters.
