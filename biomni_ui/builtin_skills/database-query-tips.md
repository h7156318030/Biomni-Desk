---
title: General practice for database queries
description: Stable ways to call the query_* tools in biomni.tool.database, and the fallback when they fail
category: Data & workflows
when_to_use: You need data from public databases such as UniProt, Ensembl, ClinVar, gnomAD, Reactome, KEGG or the GWAS Catalog
avoid: If the data are already in the local data lake, read the files directly; do not query online interfaces again
uses: query_uniprot, query_ensembl, query_clinvar, query_gnomad, query_reactome, query_gwas_catalog
---
## How to call
1. First call with the natural-language parameter `prompt=`. This depends on the interface description files that are stored locally.
2. If you get an error such as `No such file or directory ... schema_db/xxx.pkl`, an interface description file is missing. **Do not retry the same call.** Pass the REST address directly with the `endpoint=` parameter (for example UniProt: `https://rest.uniprot.org/uniprotkb/P04637`, or Ensembl: `https://rest.ensembl.org/lookup/symbol/homo_sapiens/TP53?content-type=application/json`), or request it directly with Python's `urllib` or `requests`.
3. Use only the fields the interface actually returns; do not fill in values from memory.

## Handling results
- Print the key names of the returned structure first, then take the fields you need; for long responses, print only the key parts.
- Write the interface addresses used into the final answer so that they can be checked.
- If a query returns nothing, say so plainly ("not found") and state the query conditions. Do not quietly swap in a different condition.

## Notes
- Public interfaces may rate-limit or be temporarily unavailable. When a call fails, wait and retry once; if it still fails, explain why.
