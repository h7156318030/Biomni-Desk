---
title: Audit-grade literature deep review (exact citations and evidence table)
description: Write an auditable literature review: retrieve full texts, verify each citation against the original text, build a claim-to-evidence table, and check for contradictions
category: Literature & evidence
when_to_use: The user needs a review with citations checked against the original text and traceable to sources, for example for a submission, a publication, or a legal or regulatory purpose
avoid: Conclusions from abstracts alone are unreliable, so get full texts; each citation must be checked word for word against the original, not from memory; if paid full texts cannot be accessed from this computer, say so
uses: dbtools.query_pubmed, lit.paper_abstracts, web.read_webpage, europepmc_search
chain: Upstream is the research question; downstream can be literature-review or report generation
---
## Steps
1. Search: use reproducible search strings in PubMed and Europe PMC, and record the search date and the number of results.
2. Screen: apply the inclusion criteria and record the reason for each exclusion.
3. Full texts: read open-access full texts with read_webpage or the PDF tools; mark those that cannot be obtained as "abstract only".
4. Evidence table: one row per claim, listing the sentence from the original text (quoted word for word), its location (paragraph or figure or table), and the PMID of the source.
5. Verification: spot-check that each citation matches the claim it supports; where it does not, correct the claim.
6. Contradictions: list the studies whose conclusions run in the opposite direction, and explain the likely reasons.

## Quality bar
- Citations must be checked word for word against the original; do not paraphrase and present the paraphrase as a quotation.
- Claims supported only by an abstract must be marked as such.
- Search strings and dates must be reproducible.

## Output conventions
- Table: claim, quoted original text, location, PMID, verification status.
- State the search strings, the search date, the numbers included and excluded, and the proportion of full texts obtained.
