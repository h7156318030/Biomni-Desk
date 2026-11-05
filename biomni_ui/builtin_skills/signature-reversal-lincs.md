---
title: Compound reversal of a gene signature (LINCS L1000 / CMap)
description: Query the LINCS L1000 compound perturbation profiles with up- and down-regulated gene signatures, to find small molecules that reverse or mimic the signature
category: Drug discovery & safety
when_to_use: The user has the up- and down-regulated genes of a disease (or DE results) and wants drugs that reverse that signature, or compounds that mimic the knockout of a gene
avoid: LINCS is large and needs network access or a local copy; a high reversal score is not efficacy, and follow-up validation is needed; the cell line may differ from the disease tissue
uses: needs LINCS L1000 scores or a signature library; RDKit for checking compound structures
chain: Upstream is consensus-disease-signature or the DE results from DESeq2; downstream goes to drug-bioactivity-chembl to look up targets and activity
---
## Steps
1. Prepare the signature: take 150 up-regulated and 150 down-regulated genes for the disease relative to control (ranked by FDR and effect size).
2. Query LINCS: with the up and down gene sets, calculate the connectivity score for each perturbation (compound, dose and cell line). A score close to −1 means reversal.
3. Summarise by compound (the median across cell lines and doses for the same compound), and take the top 20 with the most negative scores.
4. For the candidate compounds, look up their targets and known indications (`chembl_target_compounds`, `query_chembl`), and check whether they point in a direction consistent with the disease biology.

## Quality bar
- A reversal score measures only transcriptional similarity; it does not establish a mechanism or efficacy.
- Compare the cell lines with the disease-relevant tissue; the same compound can give opposite results in different cell lines.
- Report the data version and thresholds for the candidate compounds, and state that they have not been validated experimentally.

## Output conventions
- Table: compound, connectivity score, cell line, dose, known targets, known indications.
- State the number of signature genes, the LINCS version, the range of cell lines and the query date.
