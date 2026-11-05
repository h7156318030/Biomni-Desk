---
title: Germline and somatic variant calling from sequencing data (SNVs, indels)
description: Call SNVs and indels from FASTQ files or aligned BAM files, covering alignment, duplicate marking, calling with GATK or DeepVariant, filtering and concordance assessment
category: Genomics & genetics
when_to_use: The user has WES or WGS data and wants to call variants, or wants to compare the concordance of different calling tools
avoid: Needs a reference genome and substantial compute (GATK or DeepVariant usually need a Linux environment); these tools are not installed on this computer, so say so; somatic calling needs a paired normal sample
uses: needs BWA, samtools, GATK or DeepVariant; pysam
chain: Upstream is the raw sequencing data; downstream goes to genetic-variant-annotation and rare-disease-case-prioritization
---
## Steps
1. Alignment: align to the reference genome (GRCh38) with BWA-MEM, adding read-group information for each sample.
2. Duplicate removal and QC: mark duplicates (Picard or samtools markdup), and check the coverage and the insert size distribution.
3. Calling: GATK HaplotypeCaller (germline) or DeepVariant, producing a VCF.
4. Filtering: filter on quality, depth and strand bias; use separate thresholds for indels.
5. Concordance: compare with a gold standard (the GIAB reference samples), and calculate precision and recall (hap.py).

## Quality bar
- The reference genome version must be the same throughout, otherwise positions are shifted.
- Calls in regions with coverage below 20× are unreliable.
- Report the number of calls before and after filtering.

## Output conventions
- Table: sample, coverage, number of calls, number after filtering, precision and recall against the gold standard.
- State the reference version, the tool versions, the parameters and the date.
