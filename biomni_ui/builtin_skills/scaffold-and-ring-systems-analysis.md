---
title: Compound scaffold and ring system statistics (Bemis–Murcko)
description: Use RDKit to count the scaffolds, generic scaffolds and ring systems in a compound dataset, for assessing chemical diversity and dividing compounds into series
category: Drug discovery & safety
when_to_use: The user provides a SMILES dataset (CSV, TSV or SMI) and asks what the common scaffolds are, how diverse the compound library is, or which ring systems are most common
avoid: Rows with invalid SMILES must be reported and removed first; scaffold counts cannot tell you about activity; very large datasets should be processed in batches
uses: rdkit, pandas
chain: Upstream is the compound library or ChEMBL activity data; downstream goes to the within-series SAR analysis (chembl-hit-series-sar-docking)
---
## Steps
1. Read the SMILES, parse and standardise them, and remove invalid rows:
```python
import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
df = pd.read_csv("library.csv")
mols = [Chem.MolFromSmiles(s) for s in df["smiles"]]
valid = [m is not None for m in mols]
print("invalid:", valid.count(False))
```
2. Calculate the Bemis–Murcko scaffolds and the generic scaffolds (with atom types removed):
```python
scaf = [MurckoScaffold.MurckoScaffoldSmiles(mol=m) for m, ok in zip(mols, valid) if ok]
generic = [MurckoScaffold.MakeScaffoldGeneric(MurckoScaffold.GetScaffoldForMol(m)) for m, ok in zip(mols, valid) if ok]
```
3. Count the scaffold frequencies and list the top 20. Count the ring systems and their distribution.
4. Diversity metrics: the number of unique scaffolds as a proportion of the number of compounds, and the proportion of the most common scaffold.

## Quality bar
- Standardise stereoisomers and salts first; otherwise the same scaffold is counted as different ones.
- A high scaffold frequency does not mean that the compounds are active; interpret it together with activity data.
- Many compounds are acyclic and have an empty scaffold; count them separately.

## Output conventions
- Table: scaffold, generic scaffold, frequency, proportion.
- State the dataset size, the number of invalid SMILES, the standardisation rules and the RDKit version.
