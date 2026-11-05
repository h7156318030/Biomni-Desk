---
title: Binder and antibody design (from structure to sequence)
description: Design new binding proteins (miniproteins, nanobodies, scFv) from a target structure: backbone generation, sequence design, structure prediction and scoring
category: Molecular & protein design
when_to_use: The user has a target structure (a PDB entry, or a structure that can be predicted from UniProt) and wants to design a new binding protein or antibody
avoid: Design needs a GPU and specialised software (such as RFdiffusion, ProteinMPNN or AlphaFold); this computer usually cannot run it, so say so and give the workflow instead; design results must be validated experimentally
uses: The generative models cannot run on this computer and need external compute; locally you can use biopython and the results of protein-structure-prediction
chain: Upstream is the target structure and epitope choice (ligand-binding-mode-analysis); downstream goes to antibody-developability-humanization
---
## Steps
1. Epitope choice: on the target structure, find exposed, functionally relevant regions and list the key residues.
2. Backbone generation: use a diffusion model (RFdiffusion or RFantibody) to generate a backbone around the epitope (needs a GPU).
3. Sequence design: use a ProteinMPNN-type tool to design sequences for the backbone, and filter out low-complexity and implausible sequences.
4. Structure prediction: predict the structure of the designed sequences with AlphaFold2 or Boltz, and check that it matches the designed backbone (RMSD).
5. Scoring and selection: interface area, prediction confidence (pLDDT), hydrophobicity and immunogenicity risk. Rank the designs and pick a small number of candidates.

## Quality bar
- Without a GPU and the software above, give only the workflow and parameters, not design results.
- Check that each designed sequence is not highly similar to a human protein (immunogenicity and safety).
- Candidates need expression and binding experiments to validate them.

## Output conventions
- Table: candidate ID, sequence, predicted confidence, interface score, risk flags.
- State the tool versions, the parameters, the epitope definition and the design date.
