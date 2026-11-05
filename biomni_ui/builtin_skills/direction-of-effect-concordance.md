---
title: Should a target be inhibited or activated? (direction of effect across evidence)
description: Combine human genetics, functional screens, drug mechanism and mouse phenotypes to judge whether a target should be inhibited or activated
category: Drug discovery & safety
when_to_use: The user asks whether a target should be inhibited or activated, or whether a drug's mechanism points in the right direction, and several kinds of evidence can be combined
avoid: A single line of evidence cannot decide the direction; first establish what the allele means for the direction of effect in human genetics; this only summarises evidence and does not replace clinical judgement
uses: dbtools.gnomad_constraint, dbtools.open_targets, dbtools.chembl_target_compounds, dbtools.query_mpd or query_monarch
chain: Upstream is target-tractability-druggability; downstream goes to clinical trial design or compound selection
---
## Steps
1. For each kind of evidence, give a direction:
   - Human genetics: does a loss-of-function (LoF) variant go with higher disease risk? If so, inhibiting the target is harmful and activation is the aim. For a GWAS protective allele, what is its direction of effect?
   - Functional screens: does knockout reduce a disease-related phenotype (inhibition is beneficial) or increase it (activation is beneficial)?
   - Drug mechanism: approved or clinical inhibitors or agonists, and whether their efficacy matches that mechanism.
   - Mouse phenotypes: does the knockout mouse show a phenotype opposite to, or the same as, the disease?
2. Score each kind of evidence +1 (supports inhibition), −1 (supports activation) or 0 (no evidence, or conflicting), then combine.
3. Before combining, check that the evidence is independent: several phenotypes from the same study count as one kind of evidence.

## Quality bar
- When evidence conflicts (for example genetics supports inhibition and a drug supports activation), list the conflict explicitly; do not average it away.
- Separate LoF from gain-of-function (GoF) evidence; do not treat every loss-of-function variant as evidence for inhibition.
- State the species differences between mouse phenotypes and humans.

## Output conventions
- Table: kind of evidence, direction, source, strength (strong, moderate, weak).
- Conclusion: the recommended direction, the number of supporting lines of evidence, the conflicting evidence, and the experiments still needed.
