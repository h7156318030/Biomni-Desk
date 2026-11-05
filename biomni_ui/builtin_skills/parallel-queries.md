---
title: Run several queries in parallel
description: When the same kind of query must be repeated for several genes, variants or search strings, run them concurrently in one code cell to shorten the total time
category: Data & workflows
when_to_use: You need to run the same online query for three or more items (a gene list, several search strings, several databases), and the queries do not depend on each other
avoid: The queries depend on each other in sequence; there are only one or two items; the interface explicitly limits concurrency or requires login
uses: concurrent.futures, requests
---
## How to do it
1. Write the query for a single item as a function. The function catches its own exceptions and returns `{"id": ..., "ok": True/False, "data"/"error": ...}`, so that one failure does not stop the whole batch.
2. Run it concurrently with `concurrent.futures.ThreadPoolExecutor(max_workers=4)`. Do not exceed `max_workers=5`, so that public interfaces do not rate-limit you.
3. Put the results back in input order (use `executor.map`, or take `future.result()` in input order), then print them together.
4. List the failed items separately with the reason. You can retry the failed items once, one at a time.

## Example skeleton
```python
from concurrent.futures import ThreadPoolExecutor
import requests

def fetch(item):
    try:
        r = requests.get(f"https://rest.example.org/{item}", timeout=30)
        r.raise_for_status()
        return {"id": item, "ok": True, "data": r.json()}
    except Exception as e:
        return {"id": item, "ok": False, "error": f"{type(e).__name__}: {e}"}

items = ["A", "B", "C", "D"]
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(fetch, items))
failed = [r for r in results if not r["ok"]]
print(f"succeeded {len(results) - len(failed)} / {len(results)}")
```

## Notes
- Run concurrently only within one code execution; do not start several steps that depend on each other at the same time.
- Concurrency scrambles the order of log lines, so collect the results and print them in input order at the end.
- Record the source address of each result so that the final answer can cite it.
