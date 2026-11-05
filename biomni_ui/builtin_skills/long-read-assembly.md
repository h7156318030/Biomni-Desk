---
title: De novo long-read genome assembly (ONT, PacBio)
description: De novo assembly of selected long-read data, evaluated by read mapping back to the assembly and completeness metrics (BUSCO), with several rounds of draft polishing
category: Genomics & genetics
when_to_use: The user has long-read data and wants to assemble a new genome, or to assess the quality of an existing draft assembly
avoid: Assembly needs a lot of memory and compute (usually Linux or a server); without an assembler on this computer, only the workflow can be given; the quality of a draft must be assessed with completeness metrics
uses: Flye, hifiasm or Canu; BUSCO; minimap2
chain: Upstream is the long-read sequencing data (the selected reads); downstream goes to structural variants and annotation
---
## Steps
1. Select reads: filter out short reads (for example under 5 kb) and low-quality reads, and record the retained number of bases and the N50.
2. Assemble: de novo assembly with Flye (ONT) or hifiasm (HiFi), with the estimated genome size specified.
3. Evaluate: count the contigs, the N50 and the total length; BUSCO completeness (vertebrate or eukaryote database).
4. Polish: map the same reads back to the draft and run one or two rounds of polishing (Racon or Medaka).
5. Check: the read mapping rate, the coverage distribution, and flag contigs that look like duplications or contamination.

## Quality bar
- Reporting the N50 alone is not enough; also give the BUSCO completeness.
- Evaluate high-coverage and low-coverage regions separately.
- Run the contamination check (for example BlobTools) before reporting.

## Output conventions
- Table: assembly version, number of contigs, N50, total length, BUSCO completeness, mapping rate.
- State the number of reads, the assembler and its version, the parameters and the date.
