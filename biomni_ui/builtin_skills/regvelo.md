---
title: RegVelo regulatory RNA velocity (HPC workflow)
description: Use RegVelo to infer regulatory RNA velocity, cell fate and transcription factor perturbations from splicing data; usually run on an HPC system
category: Transcriptomics
when_to_use: The user wants a regulatory RNA velocity analysis and has splicing counts and HPC resources
avoid: Needs an HPC system and pretrained models (not supported on this computer); results from small datasets are unstable; perturbation simulations are predictions and must be validated
uses: cannot run directly on this computer; needs the RegVelo environment on the Biomni HPC or a Linux server
chain: Upstream is the splicing counts and cell type annotation; downstream goes to grn-pyscenic to compare regulatory results
---
## Steps
1. Confirm the inputs: the spliced and unspliced count matrices, the cell annotations, and the species (the supported pretrained models cover mouse and zebrafish).
2. Run the RegVelo workflow script on the HPC, and record the job ID and the resources used.
3. Results: velocities and cell fate probabilities, and the simulated results of transcription factor perturbations.
4. Compare with the velocity results from scvelo, and check that the directions agree.
5. Validate the transcription factor perturbation results against known biology.

## Quality bar
- A pretrained model applies only to its own species and tissue; outside that range it cannot be used.
- Perturbation simulations are predictions, not experimental results.
- Without an HPC system, provide the workflow only, and no results.

## Output conventions
- Figures: velocity streamline plot, fate probability plot.
- Table: predicted effects of transcription factor perturbations.
- State the model version, the species, the HPC environment and the date.
