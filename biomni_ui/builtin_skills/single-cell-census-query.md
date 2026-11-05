---
title: Querying public single-cell atlases (CELLxGENE Census)
description: Query the CZ CELLxGENE Census for a set of genes' expression across cell types, or run a donor-level pseudobulk comparison of disease versus control
category: Transcriptomics
when_to_use: The user asks in which cell types a gene is highly expressed, or how cell-type expression changes in a disease, and wants the answer from public large-scale single-cell data
avoid: On Windows, the tiledb dependency of cellxgene-census cannot be compiled on this computer, so it needs Linux or WSL; the Census is very large, so restrict the cells with filters; results depend on the composition of the datasets and are not the expression of the whole population; needs network access
uses: cellxgene_census, pandas
chain: Upstream is a gene list (for example candidates from target-tractability); downstream goes to tissue expression (tissue-expression-specificity) for an overall judgement
---
## Steps
1. Open a specified version of the Census, filter by species, tissue and disease, and take only the genes you need:
```python
import cellxgene_census
with cellxgene_census.open_soma(census_version="stable") as census:
    adata = cellxgene_census.get_anndata(
        census, organism="Homo sapiens",
        obs_value_filter="disease == 'normal' and tissue_general == 'blood'",
        var_value_filter="feature_name in ['CD19', 'CD22', 'MS4A1']",
        column_names={"obs": ["cell_type"], "var": ["feature_name"]},
    )
```
2. Calculate, for each cell type, the proportion of cells expressing the gene and the mean expression (using `adata.to_df()` and `groupby`).
3. Donor-level pseudobulk for disease versus control: sum the counts by donor and cell type, then compare with DESeq2 or pydeseq2.

## Quality bar
- State the filter conditions (species, tissue, disease, cell type) clearly, and record the number of cells. The results change with the Census version.
- Cell types with few cells give unstable statistics; set a minimum number of cells (for example 50).
- A high proportion does not mean high expression; report the proportion and the mean together.

## Output conventions
- Table: cell type, number of cells, proportion of expressing cells, mean expression.
- State the Census version, the filter conditions, the number of datasets and the query date.
