---
title: ADME single-endpoint machine learning model (training and evaluation)
description: Train, evaluate honestly and apply an ADME model from labelled experimental data (solubility, permeability, clearance, binding, CYP, hERG, BBB and similar)
category: Drug discovery & safety
when_to_use: The user has labelled data for one or more ADME endpoints and wants to train a predictive model or predict for new compounds
avoid: With fewer than about 200 labelled compounds the model is unreliable; data from different sources or under different experimental conditions must not be trained on together; a model does not replace experimental measurement
uses: rdkit, scikit-learn; chemprop optionally
chain: Upstream is the basic properties from molecular-property-admet; downstream is ranking compounds by priority
---
## Steps
1. Data preparation: SMILES, endpoint values, experimental conditions and source. Unify the units and remove duplicates and conflicting labels.
2. Features: Morgan fingerprints (radius 2, 2048 bits) plus RDKit descriptors. Split training and test sets by scaffold so that the same scaffold does not leak across the split.
```python
from rdkit import Chem
from rdkit.Chem import AllChem
import numpy as np
def fp(smi):
    m = Chem.MolFromSmiles(smi)
    return np.array(AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048))
```
3. Model: a random forest or gradient boosting as the baseline; compare with Chemprop and others. Report R² or AUC from 5-fold cross-validation, grouped by scaffold.
4. Application: predict for new compounds and give the applicability domain (the nearest-neighbour similarity to the training set).

## Quality bar
- Random splits overestimate performance; split by scaffold or by time.
- Report the baseline model's performance to show that the new model improves on it.
- Mark predictions outside the applicability domain as unreliable.

## Output conventions
- Table: endpoint, number of samples, split method, cross-validation metrics, baseline metrics.
- State the data source, experimental conditions, model type, features and versions.
