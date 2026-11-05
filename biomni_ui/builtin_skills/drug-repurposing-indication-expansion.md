---
title: Old drugs for new indications (drug repurposing)
description: Search marketed or clinical drugs for reversal of a disease's expression signature, combine target evidence and known indications, and propose testable new indication candidates
category: Drug discovery & safety
when_to_use: The user asks whether an existing drug could treat a disease, or whether an old drug could treat this condition, or already has a disease signature and wants drugs for it
avoid: A high reversal score does not mean the drug works; safety and dosage form must be checked, and the result must not be recommended to patients directly; with limited public data the conclusions are only hypotheses
uses: dbtools.open_targets, dbtools.chembl_target_compounds with query_chembl, dbtools.query_openfda or fda_adverse_events, LINCS reversal
chain: Upstream is consensus-disease-signature or DE results; downstream goes to off-target-safety-pharmacology and clinical trial design
---
## Steps
1. Disease signature: take the up- and down-regulated genes of the disease (from multi-cohort or DE results).
2. Reversal search: find compounds with the signature-reversal-lincs workflow.
3. Target evidence: for each candidate compound's targets, use open_targets to see the association with the disease.
4. Known indications: use query_chembl to look up approved indications, and compare them with the disease to avoid duplication.
5. Safety signals: use fda_adverse_events to look up adverse reactions, and find risks related to the disease's pathology.
6. Synthesis: rank by the four criteria: reversal score, target evidence, safety, and known indications.

## Quality bar
- The same compound may have several actions, and the reversal may come from an off-target effect; say so.
- Safety signals come from spontaneous reports and cannot be converted into rates.
- Label each candidate "hypothesis, to be tested", not a recommendation.

## Output conventions
- Table: candidate drug, reversal score, target evidence, known indications, safety signals, overall ranking.
- State the data versions, the query date and the assumptions.
