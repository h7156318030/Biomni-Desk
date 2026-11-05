---
title: Pathway enrichment analysis of a gene list
description: Run GO, KEGG or Reactome enrichment (Enrichr) on a set of genes, output a table and a bar plot, and report the statistics properly
category: Multi-omics
when_to_use: The user gives a set of genes (differential expression results or candidate genes) and wants to know which pathways or functions they are enriched in
avoid: Fewer than 5 genes is meaningless (the function refuses); results from fewer than 10 to 15 genes are unstable, so warn the user; for gene-set scoring (GSEA ranking analysis) use a dedicated workflow; for a custom background gene set, say that Enrichr uses a genome-wide background
uses: biomni_ui.analysis.enrich_genes, query_reactome
chain: Upstream is often the output of a differential expression analysis; downstream is a report with charts
---
## Steps
1. Confirm the type of gene symbol and the species (the function queries human gene sets). De-duplicate, remove blanks, and record the number of input genes.
2. Run (needs network access to Enrichr):
```python
from biomni_ui.analysis import enrich_genes
genes = ["TP53", "MDM2", "CDKN1A", "BAX", "BBC3", "GADD45A", "SESN1", "FAS"]
print(enrich_genes(genes, library="GO_Biological_Process_2023", out="enrich_go"))
print(enrich_genes(genes, library="KEGG_2021_Human", out="enrich_kegg"))
print(enrich_genes(genes, library="Reactome_2022", out="enrich_reactome"))
```
3. Read the results: the number of terms with an adjusted P (FDR) below 0.05, the top 10 terms, and the overlapping genes. The table is saved to `<out>_table.csv` and the plot to `<out>_bar.png`.
4. If nothing is significant, say so plainly ("no significant enrichment"); do not lower the threshold to force a result.
5. To look into a pathway or check its genes: `query_reactome(prompt="pathways involving TP53")`.

## Quality bar
- Report only the corrected P (FDR), never only the raw P.
- Run the up- and down-regulated genes **separately** if possible; mixing them lets the effects cancel out.
- Background gene set: Enrichr uses the whole genome by default. If the experiment measured only some genes (for example a targeted panel), the results are biased; say so.
- Broad general pathways (such as "cell cycle" or "immune response") cover many genes and are easily significant, so interpret them in the context of the question.

## Output conventions
- Table: pathway | overlapping or pathway gene count | FDR | hit genes.
- State the number of input genes, the database and its version, the correction method and the date.
- Enrichment describes a statistical association, not a causal conclusion.
