---
title: sgRNA design (knockout, CRISPRi, CRISPRa)
description: Design sgRNAs for a target gene, preferring validated sequences from Addgene and the literature, then design-tool scores, and check off-target sites
category: Molecular & protein design
when_to_use: The user wants gene knockout, CRISPRi or CRISPRa, and asks for the sgRNAs of a gene
avoid: The final sgRNA cannot be chosen on a single score; consider both off-target risk and whether the sequence has been validated; state the Cas protein type (SpCas9, SaCas9, Cas12a)
uses: local resource biomni/know_how/resource/addgene_grna_sequences.csv, biopython
chain: Upstream is target selection; downstream goes to pooled-crispr-screens or experimental design
---
## Steps
1. Check validated sequences first: read the local Addgene sequence table and filter for the target gene (column "Target Gene") and the Cas protein type:
```python
import pandas as pd
db = pd.read_csv("biomni/know_how/resource/addgene_grna_sequences.csv")
hits = db[db["Target Gene"] == "AAVS1"]   # replace with the target gene
print(hits[["Application", "Cas9 Species", "Target Sequence", "Plasmid ID"]])
```
2. If no validated sequence exists, generate candidates with a design tool (such as CRISPick), and rank them by score and off-target risk.
3. Check each candidate: the PAM site is correct (NGG for SpCas9), the GC content is 40–70%, and there are no runs of four or more identical bases.
4. Check the chosen sequences for off-target sites (count the mismatches against the genome), and replace any with high off-target risk.
5. Use at least 3 sgRNAs per gene, and include non-targeting controls.

## Quality bar
- State the source of each validated sequence (plasmid number, paper).
- CRISPRi and CRISPRa have different position requirements for the sgRNA (near the TSS); do not use knockout sequences for them.
- The design results are candidates only; the knockout efficiency must be verified experimentally.

## Output conventions
- Table: gene, sgRNA sequence, PAM, GC content, off-target risk, source (validated or design tool).
- State the Cas type, the control design and the versions.
