---
title: Tumour-selective surface antigen discovery (for CAR-T, ADC and bispecific antibodies)
description: Find proteins that are highly expressed on tumour cells, low in normal tissues and located on the cell surface, as candidate antigens for targeted therapy
category: Drug discovery & safety
when_to_use: The user asks which surface antigens of a tumour can be targeted, or wants candidate targets for CAR-T or ADC therapy; the input is a disease or tumour type
avoid: Surface localisation needs reliable annotation (UniProt, the Human Protein Atlas); high transcript levels do not mean the protein is on the cell surface; normal expression in vital organs must be considered
uses: dbtools.gtex_expression, dbtools.uniprot_lookup, single_cell_census_query, dbtools.open_targets
chain: Upstream is the disease name and tumour single-cell data; downstream goes to cell-therapy-car-design or target-tractability-druggability
---
## Steps
1. Candidate set: use open_targets to get targets associated with the disease, or use tumour single-cell data to get highly expressed genes.
2. Surface localisation: use uniprot_lookup to check for a transmembrane or extracellular domain and whether the subcellular localisation is the plasma membrane.
3. Tumour selectivity: use a single-cell atlas to compare expression in tumour cells with key normal cell types (such as haematopoietic, heart, liver, kidney and neural cells).
4. Normal-tissue risk: use gtex_expression to read the TPM in vital organs; list high expression in those organs as a risk.
5. Overall ranking: score the four criteria (surface localisation, which is required; tumour selectivity; normal-tissue risk; druggability) and rank the candidates.

## Quality bar
- If only RNA data are available, state that protein levels have not been verified.
- The cell composition of tumour samples affects expression ratios, so matched controls are needed.
- For targets already in the clinic, state the existing clinical data.

## Output conventions
- Table: candidate gene, surface localisation, tumour expression, normal-tissue risk, druggability, overall score.
- State the data sources, tumour type, number of samples and the date.
