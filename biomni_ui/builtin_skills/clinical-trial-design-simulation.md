---
title: Clinical trial design and power simulation (two-arm confirmatory trial)
description: Calculate the sample size and power of a two-arm trial (survival, binary or continuous endpoint), and simulate fixed or adaptive designs (interim analysis, futility boundaries)
category: Experimental design
when_to_use: The user asks how many patients the trial needs, whether the power is adequate, or what an interim analysis would change, and has already given an effect-size assumption
avoid: The effect-size assumption decides whether a trial succeeds, so it must come from a reliable source (earlier trials, the literature) and must not be inflated to make the sample size look better; this does not give ethics or registration advice
uses: scipy.stats, numpy, statsmodels
chain: Upstream is the effect-size estimate for the target and disease (for example evidence-synthesis-meta-analysis); downstream goes to pkpd and the trial execution plan
---
## Steps
1. Define the endpoint and the assumptions: a survival endpoint needs a hazard ratio and an event count; a binary endpoint needs two rates; a continuous endpoint needs a difference in means and a standard deviation.
2. Analytical sample size (continuous endpoint example, two-sided α = 0.05, power 80%):
```python
from scipy.stats import norm
import math
def n_per_arm(delta, sd, alpha=0.05, power=0.8):
    z = norm.ppf(1 - alpha/2) + norm.ppf(power)
    return math.ceil(2 * (z * sd / delta) ** 2)
print(n_per_arm(delta=5, sd=10))
```
3. Simulation: generate data under the assumed effect, repeat 5000 times, estimate the power, and compare different sample sizes.
4. Interim analysis: use O'Brien–Fleming boundaries, and check that the type I error is controlled when the trial stops early.
5. Dropout: divide the sample size by (1 − dropout rate).

## Quality bar
- The effect-size assumption needs a stated source, and a sensitivity analysis (for example an optimistic and a conservative assumption).
- Multiple comparisons and interim analyses need formal correction; do not look at the data informally.
- Report the assumptions, the formulas or the number of simulations, so that the result can be reproduced.

## Output conventions
- Table: endpoint, effect-size assumption, α, power, sample size per arm, sensitivity analysis results.
- State the method (analytical or simulation), the number of simulations and the software versions.
