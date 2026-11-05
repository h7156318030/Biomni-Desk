---
title: Clinical trial registration search and landscape
description: Search ClinicalTrials.gov registrations by disease, intervention or sponsor, and summarise phase, status, sponsors and enrolment
category: Clinical & statistics
when_to_use: The user asks which clinical trials exist for a disease or therapy, what phase they are in, who is running them, or what the registrations of a company's pipeline show
avoid: This only finds ClinicalTrials.gov registrations. Registrations in China (the CTR, the Drug Clinical Trial Registration and Information Disclosure Platform), the EU and Japan must be searched separately, and you must not say that there are "no trials" on that basis; registrations are not trial results
uses: biomni_ui.dbtools.clinical_trials, query_clinicaltrials, biomni_ui.web.web_search
chain: Upstream is often target assessment or a company search; downstream can be a report with charts
---
## Steps
1. First define the search scope: the disease (synonyms and English names), the intervention (drug names, therapy type), the status and the region.
2. Run it (once for each angle):
```python
from biomni_ui.dbtools import clinical_trials
print(clinical_trials("beta thalassemia", "gene therapy", max_results=15))
print(clinical_trials("thalassemia", "lentiviral", status="RECRUITING", max_results=15))
```
3. For key registration numbers, use `query_clinicaltrials(prompt="details of NCT04211480")` to get the protocol, endpoints and results.
4. If a company or product name does not appear on ClinicalTrials.gov, **do not conclude that there are no clinical trials**. Search the Chinese registry (registration numbers look like CTR2024xxxx) and the company's announcements by name, and state where you looked.

## Quality bar
- Report both the total number of registrations and the number listed ("35 in all, the first 15 listed").
- Write phase N/A, phase 1 and phase 1/2 exactly as registered; do not merge them.
- The status is the status at registration and may be out of date; state the query date.
- A trial that appears in several searches must be counted once (de-duplicate by NCT number).

## Output conventions
- Table: NCT number | title | phase | status | sponsor | start date | enrolment.
- One-sentence overview: the phase distribution, the main sponsors, and whether results have been posted.
