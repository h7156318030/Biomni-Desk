---
title: Bulk RNA-seq differential expression (DESeq2)
description: Run a two-group differential expression analysis on a raw count matrix, output a results table, a volcano plot and the numbers of up- and down-regulated genes
category: Transcriptomics
when_to_use: The user gives (or can obtain) a raw integer count matrix from bulk RNA-seq, with group information, and wants the differentially expressed genes between two conditions
avoid: The data are TPM, FPKM or normalised values (DESeq2 needs raw counts); a group has fewer than 2 replicates; single-cell data (use the scRNA-seq skill); only FASTQ files (there is no alignment pipeline on this computer, so say that it cannot be done rather than pretend)
uses: biomni_ui.analysis.de_deseq2, biomni_ui.analysis.enrich_genes
chain: Downstream goes to the pathway enrichment analysis of a gene list; upstream may be a GEO dataset search
---
## Inputs
- `counts.csv`: raw integer counts, genes × samples (or samples × genes). The first column holds the gene or sample names.
- `meta.csv`: one row per sample. The first column holds the sample name, and there is at least one grouping column (for example `condition`).

## Steps
1. Look at the data first: the number of rows and columns, the first few rows, and the number of samples in each group. **If any group has fewer than 2 samples, stop and say so plainly**; do not force the analysis.
2. Confirm that the values are raw counts (integers, no negatives). The function checks this; if it reports non-integer values, tell the user that raw counts are needed, and do not round them yourself.
3. Run:
```python
from biomni_ui.analysis import de_deseq2
print(de_deseq2("counts.csv", "meta.csv", condition="condition", treat="treat", ref="ctrl", out="deseq2"))
```
4. Read the results table `deseq2_results.csv` (columns: baseMean, log2FoldChange, lfcSE, stat, pvalue, padj). The default thresholds are padj < 0.05 and |log2FC| > 1; state them, and if you change them, give the reason.
5. For a pathway interpretation, pass the up- and down-regulated genes to enrichment separately:
```python
import pandas as pd
from biomni_ui.analysis import enrich_genes
r = pd.read_csv("deseq2_results.csv", index_col=0)
up = list(r[(r.padj < 0.05) & (r.log2FoldChange > 1)].index)
print(enrich_genes(up, "GO_Biological_Process_2023", out="enrich_up"))
```

## Quality bar (state any failure in the limitations)
- The number of replicates per group. With fewer than 3, the p values are unstable; say so.
- Paired design and batch: if the metadata has a batch column, state that this analysis did not correct for it (the function uses one grouping factor only).
- The number of genes tested, and the number of genes with a missing padj (lowly expressed genes filtered out).

## Output conventions
- Start with the conclusion: which two groups, how many significantly up- and down-regulated genes, and the top 5 to 10 genes (with log2FC and padj).
- Files: `deseq2_results.csv` and `deseq2_volcano.png`. Name the files in the answer.
- End with the methods: PyDESeq2, the thresholds, the number of replicates, and whether batch was corrected.

## Do not
- Do not compare counts with a t test directly; do not describe a correlation as causation; do not give a significance conclusion for data without replicates.
