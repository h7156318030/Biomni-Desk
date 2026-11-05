---
title: Public omics dataset search (GEO)
description: Search GEO for datasets by disease, cell type or technology, and check each one's species, sample number, data type and relevance to the question
category: Data & workflows
when_to_use: The user wants public transcriptome or epigenome data for a disease, cell type or treatment condition, or wants to reuse published data
avoid: Downloading and reprocessing raw SRA FASTQ files is not possible here (there is no alignment pipeline on this computer); if the data are in another repository such as ArrayExpress or CELLxGENE, search there separately and say so
uses: biomni_ui.dbtools.geo_search, query_geo
chain: Downstream goes to differential expression or single-cell analysis; upstream is the research question
---
## Steps
1. Split the question into: species, tissue or cell type, disease or treatment, and technology (RNA-seq, scRNA-seq, ATAC).
2. Search (try several sets of keywords):
```python
from biomni_ui.dbtools import geo_search
print(geo_search("CAR-T exhaustion single cell", max_results=10))
print(geo_search("CAR T cell Homo sapiens[Organism] AND expression profiling by high throughput sequencing[DataSet Type]", 10))
```
   GEO syntax: `xxx[Organism]`, `2022:2026[Publication Date]`, `gse[Entry Type]`.
3. **Check each dataset's relevance**, not just its title. Open `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE…` to read the summary, the groups and the samples, or read it with `read_webpage`.
4. Give the user a table grading each dataset as recommended, usable or not relevant, with the reasons.

## Quality bar
- Verify the sample numbers, the species, and whether a usable processed matrix (supplementary files) is available.
- Distinguish raw counts from normalised values; differential expression needs raw counts.
- Datasets may include duplicate submissions or sub-series; de-duplicate them.
- State that only GEO was searched, and that other repositories were not covered.

## Output conventions
- Table: GSE | title | species | sample number | type | date | relevance (high, medium, low) | reason.
