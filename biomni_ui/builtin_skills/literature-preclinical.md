---
title: Preclinical evidence review (target and disease)
description: For one target and one disease, search and summarise the evidence from in vitro, animal model and human data, graded by strength of evidence
category: Literature & evidence
when_to_use: The user asks whether a target has preclinical evidence in a disease, what animal models show, or how strong the evidence is
avoid: To summarise clinical trial results, use the clinical trials skill; for a quantitative pooled estimate, use the meta-analysis skill and first extract the numbers paper by paper; if you only want one person's papers, use the author papers search
uses: biomni_ui.lit.pubmed_search, biomni_ui.lit.paper_abstracts, biomni_ui.lit.europepmc_search
chain: Upstream is often target assessment; downstream is a report with charts
---
## Steps
1. Write the search string and explain each part: the target (gene name and aliases) AND the disease (including synonyms) AND study-type terms. For example:
```python
from biomni_ui.lit import pubmed_search, paper_abstracts, europepmc_search
print(pubmed_search('(PCSK9[Title/Abstract]) AND (hypercholesterolemia[Title/Abstract]) AND (mouse OR knockout OR inhibitor)', 15))
print(europepmc_search("PCSK9 hypercholesterolemia mouse", 10, since="2022-01-01"))   # includes preprints; label them as not peer reviewed
```
2. Select 8 to 15 directly relevant papers, and fetch their abstracts in one call: `paper_abstracts("PMID1,PMID2,...")`.
3. Record each paper: the model (cell line, primary cells, mouse strain or large animal), the intervention (knockout, inhibitor, dose), the readout (the measure), the direction and size of the result, the sample size (write "not given in abstract" if the abstract does not give it), and the PMID.
4. Write up by evidence strength: **human genetics and clinical samples > in vivo models > in vitro cells > correlation alone**. For each level, give the number of papers, and flag contradictory and negative results.

## Quality bar
- Conclusions drawn from abstracts only must be labelled "abstract only"; do not add details that are not in the abstract.
- Negative or null results must be searched for (add terms such as "no effect", "failed", "did not"), and you must say whether any were found.
- Animal strains, doses and routes of administration differ, so do not compare effect sizes directly.
- Label preprints separately; review articles are not original evidence.

## Output conventions
- Start with a one-sentence judgement (strong, moderate, weak or contradictory) and the main reasons.
- Evidence table: PMID | model | intervention | readout | result | level.
- Limitations: the search string, the date, abstract-only reading, and possible omissions.
