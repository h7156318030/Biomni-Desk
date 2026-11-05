---
title: Fine-mapping of a GWAS locus (SuSiE)
description: Fine-map a single GWAS locus with SuSiE, giving each variant's posterior inclusion probability (PIP) and the 95% credible sets
category: Genomics & genetics
when_to_use: The user has summary statistics for one GWAS locus and asks which variant is most likely causal, or which variants are in the credible sets
avoid: An LD reference matched to the ancestry of the sample is required, otherwise the results are unreliable; with several causal variants in strong LD the resolution is limited; a PIP alone does not establish function
uses: susieR, or a Python implementation of SuSiE; the LD matrix needs a reference panel
chain: Upstream is the GWAS summary statistics; downstream goes to gwas-to-function-twas and functional annotation
---
## Steps
1. Extract the locus: take the variants within ±500 kb of the index SNP. Each variant needs a beta, a standard error and an allele frequency.
2. LD matrix: compute the LD from a reference panel matched to the ancestry of the GWAS, and check its consistency with the GWAS data (LD mismatch diagnostics).
3. Run SuSiE with L causal signals (usually L = 10). This gives each variant's PIP and the 95% credible sets.
4. Check convergence and the purity of the credible sets (the minimum correlation).
5. Functionally annotate the variants in the credible sets (genetic-variant-annotation).

## Quality bar
- The ancestry of the LD reference must match the GWAS.
- Report the number and purity of the credible sets; when purity is low, say that the causal variant cannot be identified.
- A variant with a high PIP still needs functional experiments to validate it.

## Output conventions
- Table: variant, position, PIP, the credible set it belongs to, annotation.
- State the GWAS source, the sample size, the LD reference, the value of L and the software version.
