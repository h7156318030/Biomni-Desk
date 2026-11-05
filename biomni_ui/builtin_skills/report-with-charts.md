---
title: Report with charts, figures and a check table
description: Turn search and analysis results into a report file with charts, a check table and a list of sources
category: Reports
when_to_use: The user asks for a "detailed report", a "report with charts", for results to be organised into a report, or for checks followed by a report; or the task itself needs several data points compared and a deliverable file produced
avoid: Questions that need only a sentence or two of answer; do not force a chart when the data are unreliable (not found or the source is unclear)
uses: biomni_ui.report.make_chart, biomni_ui.report.build_report
chain: Before this, use the literature summary or a web search to get the data
---
## How to do it
1. **Get the data first, then draw the charts.** Every number must come from this task's tool output (search results, pages read, data files). Record the source of each number (PMID, DOI or URL). If a number cannot be obtained, write "not obtained"; do not estimate it.
2. **Check table.** For each statement the user has questioned or that needs checking, build a table: `statement | original source text | verdict`. Use three verdicts only: ✅ consistent with the source; ⚠ partly consistent (say where it differs); ❓ cannot be verified. For a list of papers or facts, use "confirmed / highly likely / to be checked" in the same way, and give the basis.
3. **Charts.** Each chart shows one conclusion; use `make_chart`. Use bar or line charts where they make the point clearly, and avoid pie charts. Label the axes with units. The chart title should state the conclusion (for example "Net loss rose 42% from 2024 to 2025"). Images are saved in the current folder.
4. **Write the report.** Call `build_report(title, summary, sections, sources=...)` once. Structure: summary (3 to 5 sentences, conclusion first), then the check table, then thematic sections (text, table and figure), then limitations and items still to be verified, then sources.
5. **In the reply**: give the conclusion and the report file name in a few sentences, and list the two or three most important findings. Do not paste the whole report again.

## Example
```python
from biomni_ui.report import make_chart, build_report
f1 = make_chart("bar", ["Year 1", "Year 2"], [1.2, 1.8], title="Net loss (USD million)", ylabel="USD million")
print(build_report("Financial review of Company X", "Cumulative loss over two years is about USD 3.0 million ...",
    [{"heading": "Check table", "table": [["Statement", "Original source text", "Verdict"], ["Two-year loss of about USD 3 million", "1.2 + 1.8 = 3.0 (prospectus, page 12)", "✅"]]},
     {"heading": "Loss trend", "text": "- Year 2 loss was about 50% higher than Year 1", "figure": f1, "caption": "Net loss (USD million)"}],
    sources=["Prospectus, https://example.org/prospectus (placeholder)"]))
```
