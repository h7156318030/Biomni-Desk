---
title: Immune repertoire analysis (TCR-seq, BCR-seq)
description: Analyse TCR or BCR repertoires from 10x V(D)J, immunoSEQ, MiXCR or AIRR-format data: clonotypes, clonal expansion, diversity, shared CDR3 sequences and V/J usage
category: Transcriptomics
when_to_use: The user has immune repertoire data and asks about clonal expansion, how diverse the repertoire is, or whether V/J usage differs between groups
avoid: Diversity is not comparable when sequencing depth is too low, so subsample first; judging whether a clone is public needs database support; this does not predict antigen specificity
uses: scirpy, pandas
chain: Upstream is the Cell Ranger VDJ or MiXCR output; downstream can be integration with single-cell transcriptomics
---
## Steps
1. Read: load the AIRR-format table, and check the CDR3 amino-acid sequences and the V and J gene annotations.
2. Clonotypes: define clones by the CDR3 amino acid sequence and the V/J genes, and count the reads of each clone.
3. Expansion: the proportion of the largest clone, and the distribution of clonal expansion.
4. Diversity: Shannon and Chao1, after rarefying to a common depth.
5. Sharing: the number of public clones (identical CDR3) shared between samples.
6. V/J usage: compare the usage frequency of each gene between groups.

## Quality bar
- Samples with different depths must be rarefied before their diversity is compared.
- Check the CDR3 sequences of public clones for common sequences or contamination.
- For single-cell data, count clones by cell rather than by read.

## Output conventions
- Figures: bar chart of clonal expansion, heatmap of V/J usage.
- Table: number of clones per sample, proportion of the largest clone, diversity indices.
- State the data format, the rarefaction depth, the clone definition and the date.
