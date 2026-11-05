---
title: Drug adverse event signals (FAERS)
description: Use openFDA to get the most frequently reported adverse reactions for a drug, with report counts, and explain the limits of spontaneous reporting
category: Drug discovery & safety
when_to_use: The user asks which common adverse reactions or safety signals a drug has, and wants to know what has been reported after marketing
avoid: Incidence, relative risk or causality cannot be calculated (FAERS is spontaneous reporting with no denominator); comparing the safety of two drugs needs disproportionality analysis with correction, which this skill does not do, so only describe them side by side
uses: biomni_ui.dbtools.fda_adverse_events, query_openfda
chain: Can be written into a report together with the drug label (DailyMed) and the safety data from clinical trials
---
## Steps
1. Use the **generic English name in capitals** for the drug (for example `PEMBROLIZUMAB`). If the user gives a Chinese name, translate it first and have the user confirm.
2. Run:
```python
from biomni_ui.dbtools import fda_adverse_events
print(fda_adverse_events("PEMBROLIZUMAB", top=15))
```
   The result gives the total number of reports and the most frequent MedDRA reactions with their report counts.
3. For a breakdown of one reaction (by age, severity or concomitant drugs), use `query_openfda(prompt="...")`, or add fields such as `patient.patientsex` or `serious` to the search.

## Quality bar (must appear in the answer)
- **A report count is not an incidence rate.** There is no count of exposed patients as a denominator. Well-known drugs, new drugs and drugs in the news receive more reports (stimulated reporting).
- **A report is not causation.** When "disease progression", "no drug effect" or "use outside the indication" tops the list, the report is describing the underlying disease, not drug toxicity.
- The same event may be reported more than once, and a reaction under combination therapy cannot be attributed to a single drug.
- Inconsistent drug names cause missed reports: try both the brand name and the generic name before saying that there are "no reports".

## Output conventions
- Table: reaction, report count. For the top 3 to 5 reactions, explain in one sentence what kind each is (drug-related, underlying-disease-related, or a medication-use problem).
- End with the fixed statement: "Data from openFDA FAERS spontaneous reports; these do not represent incidence or causation."
