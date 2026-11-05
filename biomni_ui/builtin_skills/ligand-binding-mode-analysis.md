---
title: Ligand binding mode analysis (co-crystal structures)
description: Analyse how a ligand binds a protein from a PDB co-crystal structure: pocket residues, heavy-atom contacts, hydrogen bonds and key interactions
category: Molecular & protein design
when_to_use: The user gives a PDB identifier or a structure file and asks how the ligand binds or which residues are key
avoid: For low-resolution structures or ligands with weak electron density, state the limitation; hydrogen positions usually have to be inferred; this does only geometric analysis, not energy calculation
uses: biopython, rdkit, numpy; biotite optionally
chain: Upstream is the target structure; downstream goes to sgrna design or to the SAR interpretation in molecular design
---
## Steps
1. Read the structure: download the PDB file from RCSB, and record the resolution and the three-letter code of the ligand.
2. Find the pocket: the protein residues within 5 Å of the ligand atoms are the pocket residues.
3. Interactions: hydrogen bonds (donor–acceptor distance about 2.5–3.5 Å), hydrophobic contacts (within about 4 Å), and salt bridges (charged groups within 4 Å).
```python
from Bio.PDB import PDBParser, NeighborSearch
parser = PDBParser(QUIET=True)
structure = parser.get_structure("complex", "1abc.pdb")
atoms = list(structure.get_atoms())
ns = NeighborSearch(atoms)
```
4. Output a table of key residues and a list of interactions (a text table is enough).

## Quality bar
- For structures with a resolution worse than 3 Å, mark the interaction assignments as uncertain.
- Describe different conformers or multiple occupancy states of the ligand separately.
- Hydrogen-bond assignments rely on geometry and do not represent actual energetic contributions.

## Output conventions
- Table: residue, interaction type, distance, atoms.
- State the PDB identifier, the resolution, the ligand code and the analysis date.
