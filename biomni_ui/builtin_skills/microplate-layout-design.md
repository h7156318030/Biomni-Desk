---
title: Microplate layout design
description: Generate a randomised layout for a 96- or 384-well plate: leave the edge wells empty, spread the controls out, keep replicates apart, and export a table
category: Experimental design
when_to_use: The user wants to place the samples, controls and replicates on one plate, and wants to reduce edge effects and position bias
avoid: Serial-dilution layouts and designs that balance several plates across batches are not covered (this skill only randomises a single plate, and should say so)
uses: biomni_ui.analysis.plate_layout
chain: Upstream can be the sample size calculation; the result goes to the lab staff who run the plate
---
## Steps
1. Ask first: the plate format (8×12 = 96 wells, or 16×24 = 384 wells), the sample list, the number of replicates for each sample, and which controls to include.
2. Run:
```python
from biomni_ui.analysis import plate_layout
print(plate_layout(["S1", "S2", "S3", "S4"], replicates=3, controls=["negative control", "positive control", "blank"], rows=8, cols=12, out="plate", seed=1))
```
3. Read the return value: how many wells were used. If there are not enough inner wells, the function reports an error; in that case reduce the samples or replicates, or switch to a 384-well plate (`rows=16, cols=24`).
4. Open `plate.csv`, where the rows are A–H and the columns are 1–12. Give a readable layout table (or quote the key rows), and save the random seed so that the layout can be reproduced.

## Quality bar
- The edge wells (the first and last rows and columns) are left empty as a buffer, to reduce evaporation-driven edge effects. If the user wants the whole plate filled, state the risk.
- Replicates are spread out, but this does not guarantee balance in every row and column; for assays sensitive to column effects, use a blocked randomisation instead.
- The seed must be kept; a different seed produces a different layout.

## Output conventions
- A layout table, plus a well list (sample, replicate number, well), in the file `plate.csv`; state the seed and the plate format.
