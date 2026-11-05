---
title: From FASTQ to a count matrix (bulk RNA-seq)
description: Convert raw bulk RNA-seq FASTQ files, or SRA, ENA or GEO accessions, into a gene count matrix ready for differential analysis, using STAR or Salmon
category: Transcriptomics
when_to_use: The user has only raw sequencing data and needs a gene count matrix before differential analysis
avoid: Alignment and quantification need a reference genome and substantial memory (usually Linux or a server); without STAR or Salmon on this computer, only the workflow can be given; confirm the strandedness first
uses: fastp or FastQC, STAR or Salmon, tximport, SRA Toolkit
chain: Upstream is the SRA or GEO accession; downstream goes to bulk-rnaseq-counts-to-de-deseq2
---
## Steps
1. Download: fetch the FASTQ files for each accession (SRA Toolkit or ENA), and record the sample and library information.
2. Quality control and trimming: check with FastQC; remove adapters and low-quality bases with fastp.
3. Quantification: align with STAR and count with featureCounts, or quantify with Salmon and summarise to gene level with tximport.
4. Merge: combine the counts of all samples into one matrix, and check the correlation between samples and the total counts.
5. Strandedness: confirm the library type (forward, reverse or unstranded) and set the counting parameters.

## Quality bar
- Report each sample's alignment rate and the number of detected genes; remove or flag abnormal samples.
- The versions of the reference genome and the annotation must match.
- A differential analysis without replicate samples has weak statistical power.

## Output conventions
- Table: sample, number of reads, alignment rate, number of detected genes.
- State the reference version, the alignment and quantification tool versions, the strandedness setting and the date.
