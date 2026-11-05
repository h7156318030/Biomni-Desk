---
title: Author papers and identity check (people with the same name)
description: Find a person's papers, separate people with the same name using ORCID, co-authors and affiliation, and find the preprints that PubMed does not index
category: Literature & evidence
when_to_use: The user asks which papers a person has published, especially with a Chinese name or a common English name that several people share
avoid: For papers on a topic, use the literature search skill instead; if the user already gave an ORCID or an affiliation, use it first to narrow the search
uses: biomni_ui.lit.author_papers, biomni_ui.lit.identity_sources, biomni_ui.lit.openalex_profile
chain: Downstream can be a report with charts (a table of papers)
---
## Steps
1. Get the identity evidence first, then the papers, not the other way round:
```python
from biomni_ui.lit import identity_sources, author_papers, openalex_profile
print(identity_sources("Li Xiaohua"))     # works and affiliations the person lists in ORCID, Semantic Scholar, Zenodo archive
print(author_papers("Li Xiaohua", compact=True, max_groups=12, per_group=40))   # PubMed, grouped by co-authors into "possible people"
```
2. **ORCID is the strongest evidence.** In an ORCID record, the works the person lists and the employment affiliations belong to the same person. PubMed clusters, OpenAlex profiles and Zenodo records that match them by co-authors or affiliation are added to that person.
3. OpenAlex (`openalex_profile`) is supporting evidence only. Its profiles come from an algorithm and **often merge people with the same name** (observed: one employee's profile mixed in toxicology papers from another university). Check the "affiliation on this paper" for each paper, and split the profile if they disagree.
4. With an ORCID, `author_papers("name", affiliation="affiliation A | affiliation B")` can also pick up older papers that list only the surname and initials.
5. Preprints (Zenodo, arXiv, bioRxiv) are not in PubMed. List them separately and note that they have not been peer reviewed.

## Quality bar
- When several people share the name, **list the candidates first (affiliation, field, number of papers, ORCID) and say which one is most likely**. Do not mix everyone's papers into one table. If the evidence is weak, ask the user for an affiliation or an ORCID.
- "Confirmed" only means the paper appears in the author's own ORCID record. It does not mean the original paper was read and checked; say so.
- The research areas the user saved are only a weak hint. Use them to order candidates only when the evidence is equal.

## Output conventions
- Candidate table, then the journal paper table for the most likely person (year, journal, title, PMID or DOI, judgement and basis), then the preprint table, then the CSV file name.
