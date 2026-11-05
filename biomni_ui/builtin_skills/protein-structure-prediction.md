---
title: Protein sequence, structure and domain lookup
description: Get protein information from UniProt, domains from InterPro, and already-solved structures from the PDB; this does not predict structures
category: Molecular & protein design
when_to_use: The user asks about a protein's function, length, domains, or whether crystal or cryo-EM structures exist, or about a structure with a bound ligand or DNA
avoid: Predicting new structures or structures after mutation is not possible here (AlphaFold and ESMFold are not available on this computer; say that only existing structures can be looked up); docking and binding-energy calculations are not covered
uses: biomni_ui.dbtools.uniprot_lookup, and the tools query_interpro and query_pdb through run_tool (these are tools, not importable functions)
chain: Downstream can be target assessment and PCR or CRISPR design
---
## Steps
1. Confirm the protein:
```python
from biomni_ui.dbtools import uniprot_lookup
print(uniprot_lookup("gene_exact:TP53", 3))        # reviewed human entries: accession, gene, name, length, function
```
2. Domains: `run_tool('query_interpro', {"prompt": "domains of human TP53 P04637"})` (a tool call; do not write `from ... import query_interpro`). From the returned JSON, read `metadata.name` (the family or domain name) and the `start` and `end` in `entry_protein_locations[].fragments` (the positions on the sequence). Write the position numbers exactly as returned; do not estimate boundaries yourself.
3. Existing structures: `run_tool('query_pdb', {"prompt": "human p53 structures bound to DNA with resolution better than 3 A"})`. The result is a list of PDB IDs. For each ID of interest, look up the details, and report: the method (X-ray, cryo-EM or NMR), the resolution, whether a ligand or DNA is bound, and the publication year.
4. Sequence: `https://rest.uniprot.org/uniprotkb/P04637.fasta`.

## Quality bar
- Distinguish the **full-length protein** from **fragments covered by a structure** (in the PDB, often a single domain).
- A smaller resolution number is better; be cautious about details worse than 3.5 Å.
- Only UniProt "reviewed" entries are manually curated; state when an entry is unreviewed.
- Confirm the species, because many genes share names between human and mouse.

## Output conventions
- Protein card: accession, gene, length, function (one sentence); domain table; structure table (PDB ID, method, resolution, ligand).
- State that the structures were determined experimentally, not predicted.
