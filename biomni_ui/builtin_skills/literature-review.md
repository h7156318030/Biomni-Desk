---
title: Literature search and key-point summary
description: Search PubMed and preprints, and give key points with sources that can be checked
category: Literature & evidence
when_to_use: The user wants to understand recent research on a topic, the literature evidence for a gene or disease, or needs sources to cite
avoid: A single known fact (query the database directly); if the user needs the strict methods of a systematic review, say that this workflow is not a systematic review; to find one person's papers, use author_papers instead of this workflow
uses: biomni_ui.lit.pubmed_search, biomni_ui.lit.paper_abstracts, biomni_ui.lit.europepmc_search
chain: Can supply literature evidence for any conclusion-based analysis
---
## Steps
1. Split the question into search terms: the core object (gene, disease or drug), the relationship (regulation, risk, efficacy) and the limits (species, time).
2. Search with `pubmed_search` (about 2–4 seconds). It prints the PMID, title, authors, journal, year and DOI, newest first. State the search string, for example `APOE4[Title/Abstract] AND Alzheimer disease[MeSH]`; to limit by date, use `("2026/01/01"[dp] : "2026/10/28"[dp])`. If there are too few results, broaden the search; if there are too many, add limits.
3. When you need abstracts, pass the 5 to 10 selected PMIDs to `paper_abstracts("PMID1,PMID2,…")` in one call; do not call it once per paper.
4. To include preprints (bioRxiv, medRxiv and others), add one `europepmc_search(query, since="YYYY-MM-DD")` call; label preprints as "not peer reviewed".
5. Group the key points by theme, and cite the PMID after each point. Do not put into the conclusions anything that the abstracts do not say.

## Output conventions
- Start with 3 to 5 sentences of conclusion, then the key points by theme, each with its PMID.
- At the end, list the search string, the search date (use today's date given in the prompt), the number of hits and the number included.
- State the limitations plainly: only abstracts were read, the coverage of the databases, and the newest preprints may be missed.

## Notes
- Do not invent PMIDs, authors or data; if nothing is found, say so.
- Copy effect sizes and sample sizes from the abstract exactly; do not calculate them yourself.
- The older function `query_pubmed` is slow (up to 80 seconds per call) and does not return authors or PMIDs. Do not use it unless the functions above fail.
