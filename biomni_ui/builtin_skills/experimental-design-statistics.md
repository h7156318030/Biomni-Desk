---
title: Sample size and power calculation
description: Calculate the sample size or number of events needed for a two-group continuous comparison, a comparison of two proportions, or a survival endpoint (hazard ratio)
category: Experimental design
when_to_use: The user is designing an experiment or a clinical trial and asks how many samples or events each group needs, or whether the power is adequate
avoid: Complex multi-factor designs, clustering or repeated measures, and non-inferiority or equivalence designs (state that this skill covers only simple cases and suggest a statistician); without a basis for the effect size, first agree with the user on a minimum meaningful difference
uses: biomni_ui.analysis.power_sample_size
chain: Downstream can be microplate-layout-design; the result must be written into the protocol
---
## Steps
1. Settle three things with the user: **the type of test** (two continuous groups, two proportions, or survival); **the minimum meaningful effect** (Cohen's d; two proportions; or the hazard ratio, HR); and **α and power** (default two-sided 0.05 and 0.8). If the effect has no basis, give a table for small, medium and large effects, rather than a single number.
2. Run:
```python
from biomni_ui.analysis import power_sample_size
print(power_sample_size("ttest", 0.5))                     # d=0.5 -> 64 per group
print(power_sample_size("proportion", 0.5, p0=0.3))        # 50% vs 30%
print(power_sample_size("survival", 0.7, p0=0.6))          # HR=0.7, expecting 60% of patients to have an event
```
3. Run it with several effect sizes and tabulate the results (for example d = 0.3, 0.5, 0.8).
4. Inflate for the expected dropout: `sample size per group ÷ (1 − dropout rate)`, and state the dropout assumption.

## Quality bar
- For a survival endpoint the calculation gives the **number of events**, not the number of patients. Convert to patients by dividing by the event rate, and state where the event rate comes from.
- If the effect size comes from a pilot study, the pilot is small and its estimate is optimistic; leave a margin.
- Several endpoints or several interim analyses need α corrected; this function does not do that.

## Output conventions
- One concluding sentence, a table of effect size against sample size, and a list of assumptions (α, power, variance or event rate, dropout).
- State clearly that this is the result of simplified formulas, and that a formal protocol needs a statistician's review.
