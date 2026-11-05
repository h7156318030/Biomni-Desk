---
title: Tissue expression specificity (GTEx)
description: Look up a target's median expression across tissues (GTEx v8 TPM), and judge whether it is concentrated in certain tissues, to assess the safety of targeting it
category: Drug discovery & safety
when_to_use: The user asks in which tissues a gene is expressed, whether targeting it would harm normal tissues, or whether it is tissue-specific; or a safety check within a target assessment
avoid: GTEx samples come from healthy adults and do not represent expression in tumours or in disease; cell-type specificity at the single-cell level needs a single-cell atlas, not tissue data alone
uses: biomni_ui.dbtools.gtex_expression
chain: Upstream is often target druggability (target-tractability-druggability); downstream can be genetic constraint (genetic-constraint-gating) for an overall safety judgement
---
## Steps
1. Get the tissue expression for a gene symbol:
```python
from biomni_ui.dbtools import gtex_expression
print(gtex_expression("CD19"))
```
   The output gives the median TPM for the top 12 tissues, the proportion of the total that the highest tissue accounts for, and a judgement of either "highly concentrated" or "broadly distributed".
2. Interpretation:
   - When the proportion is high (for example above 40%) and the high-expression tissues are unrelated to the disease, targeting those tissues is a safety risk, and it must be stated in the answer.
   - When the distribution is broad, list the organs that could be affected, and say whether they are critical for function.
3. When you need single-cell resolution, add it with a single-cell query such as `single_cell_census_query` (see the related skills).

## Quality bar
- TPM values are medians, and individuals vary considerably; read values for tissues with small samples (such as Fallopian_Tube) with caution.
- A haematopoietic target (such as CD19) is expected to be highly expressed in lymphoid tissue; this is not evidence that it is unsafe. Judge it against the disease being targeted.
- Low expression does not mean unimportant: some key proteins act in tissues where they are expressed at low levels.

## Output conventions
- Table: tissue, TPM, proportion.
- State the data version (GTEx v8), the gene version (for example ENSG00000177455.12) and the query date.
