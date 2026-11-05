---
title: CAR design and CRISPR screen review (CAR-T)
description: Design a scFv-based CAR construct (hinge, transmembrane domain, costimulatory domain, signalling domain), and use CRISPR knockout screen results in T cells to review the target and the functional genes
category: Genomics & genetics
when_to_use: The user wants to design a CAR construct, compare combinations of hinge and costimulatory domains, or wants to check CAR-T proliferation and persistence genes using CRISPR screen results
avoid: Construct design must be validated experimentally; do not give clinical-grade sequences directly; false positives in a CRISPR screen must be corrected with MAGeCK; check the source of every construct sequence
uses: dbtools.uniprot_lookup, dbtools.gtex_expression, biopython
chain: Upstream is the target selected by cell-surface-antigen-discovery; downstream goes to pooled-crispr-screens for review
---
## Steps
1. Choose the target and the scFv source (a published or approved sequence; record the source and identifier).
2. Assemble the components: signal peptide, scFv (VL-linker-VH), hinge, transmembrane region, costimulatory domain (such as 4-1BB or CD28), then CD3ζ. Choose common combinations from the literature, and state the reason.
3. Check each component's sequence (UniProt or GenBank). Annotate the domain boundaries, and check for unexpected stop codons or internal restriction sites.
4. Check expression and safety of the components: the target's normal-tissue expression (gtex_expression).
5. If there is a CRISPR screen, follow the pooled-crispr-screens workflow to find genes that affect CAR-T proliferation, and use them to choose engineering sites.

## Quality bar
- Sequences must match the literature or the database; do not assemble them from memory.
- Compare the chosen combination with approved products and explain the differences.
- Every construct needs in vitro and animal validation; state this in the answer.

## Output conventions
- Table: component, source, sequence identifier, domain boundaries, reason.
- State the design version, the source papers, the checks performed and the experiments still needed.
