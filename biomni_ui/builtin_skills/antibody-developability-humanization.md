---
title: Antibody developability and humanization (sequence check)
description: Assess the sequence developability of an existing antibody (aggregation, oxidation, deamidation sites, immunogenicity) and humanize it by CDR grafting
category: Molecular & protein design
when_to_use: The user has the VH/VL sequence of a murine or chimeric antibody and asks whether it can be developed into a drug, or how to humanize it
avoid: Immunogenicity prediction is only a risk flag and needs in vivo validation; affinity after humanization must be measured again; check where the sequences come from
uses: biopython and local sequence-check rules; human germline sequences come from the IMGT or UniProt databases
chain: Upstream is the source of the antibody sequence; downstream goes to binder-antibody-design or expression validation
---
## Steps
1. Organise the sequences: VH and VL, with CDR1–3 and the framework regions annotated by IMGT numbering.
2. Developability checks:
   - Deamidation sites (NG and NS motifs) and isomerisation sites (DG).
   - Oxidation sites (exposed methionine; tryptophan in a CDR).
   - Hydrophobic patches (runs of hydrophobic residues in a CDR).
   - Free cysteines (unpaired cysteines).
3. Humanization: find the human germline sequence most similar to the antibody's framework, graft the CDRs onto the human framework, and keep the key back-mutations (framework residues that affect CDR conformation).
4. Immunogenicity: check for T-cell epitopes (an MHC-II prediction tool can be used, once installed).

## Quality bar
- Affinity after humanization must be verified experimentally; computation cannot guarantee it.
- Each back-mutation must have a stated basis; do not keep or drop them arbitrarily.
- An immunogenicity risk is only a warning, not a finding of safety or unsafety.

## Output conventions
- Table: sequence position, risk type, location (CDR or framework), suggested change.
- State the germline source, the list of back-mutations, the tool versions and the date.
