---
title: Comparison and selection of computational methods and tools
description: Compare several computational methods or software packages that solve the same problem, and recommend one by use case, evidence, dependencies and availability
category: Literature & evidence
when_to_use: The user asks which method or tool to use for a task, what the difference between A and B is, or which one suits their data
avoid: If the user has already chosen a method and only wants it run, just run it; running a benchmark yourself is beyond this computer's compute and data (say so); purely promotional comparisons
uses: biomni_ui.lit.europepmc_search, biomni_ui.lit.pubmed_search, biomni_ui.web.web_search, biomni_ui.web.read_webpage
chain: Downstream is the specific analysis skill
---
## Steps
1. Ask or infer first: the data type and scale, the species, the goal, the hardware and software limits, and whether R or Python is required. If none is given, proceed with the common case and state the assumptions.
2. Find candidates: independent benchmark studies (search for `benchmark`, `comparison` or `evaluation` together with the method category) come before the original papers of individual methods.
```python
from biomni_ui.lit import europepmc_search
print(europepmc_search("benchmark single-cell batch integration methods", 10, since="2021-01-01"))
from biomni_ui.web import web_search, read_webpage
print(web_search("scib benchmark batch integration github", 6, "en"))
```
3. For each candidate, record: the original paper, the date of its last update (check the repository), the language and dependencies, the upper limit on scale, the inputs and outputs, and whether it is still maintained. **Verify software maintenance status; do not rely on memory.**
4. Organise the conclusions of independent benchmarks by scenario ("for large data use X, for small data use Y"), and distinguish the authors' own claims from third-party evaluations.

## Quality bar
- Benchmark conclusions depend on the datasets and metrics, and different benchmarks can rank methods differently; state which benchmark each conclusion comes from.
- Do not write version numbers, performance figures or licences that you have not verified.
- Whether it runs on this computer: Windows, no GPU, limited memory. State when a tool needs Linux or a GPU.

## Output conventions
- Give the recommendation and its conditions first, then a comparison table: method | suitable scenario | evidence source | strengths | limitations | availability on this computer.
- Include the source links and the search date.
