---
title: From a GWAS locus to candidate genes (TWAS)
description: Map GWAS associations to gene expression with transcriptome prediction models (such as GTEx or a single-cell reference), and find candidate causal genes whose expression relates to the trait
category: Genomics & genetics
when_to_use: The user has GWAS summary statistics and asks which gene a locus affects, or which genes' expression is associated with disease risk
avoid: The tissue of the expression prediction model must be relevant to the disease; TWAS shows association, not causation; the LD and the reference panel must match
uses: needs FUSION, S-PrediXcan or another TWAS tool; GTEx prediction weights must be downloaded; pandas for organising results
chain: Upstream is the GWAS summary statistics and fine-mapping (fine-mapping-susie); downstream goes to target-tractability-druggability
---
## Steps
1. Choose the tissue: expression prediction weights (GTEx) for a tissue relevant to the disease, such as blood or liver.
2. Run the TWAS: each gene's Z score is the association between its predicted expression and the trait, corrected with an LD reference.
3. Multiple testing: Bonferroni or FDR, and keep the significant genes.
4. Colocalisation: for each significant gene, check whether the GWAS and the expression QTL share a causal variant (for example with coloc), to rule out false positives caused by LD.
5. Summarise the candidate genes and compare them with the variants from fine-mapping.

## Quality bar
- A TWAS in only one tissue can miss signals in other tissues.
- Significant genes must be colocalised; otherwise the association may be an LD or eQTL artefact.
- The training sample size of the prediction model affects accuracy; report it.

## Output conventions
- Table: gene, tissue, Z score, p value, colocalisation probability, candidate grade.
- State the GWAS source, the expression model and its version, the LD reference and the date.
