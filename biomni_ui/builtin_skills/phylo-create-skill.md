---
title: Create and revise Biomni skills (skill writing standard)
description: Write or change a skill document in the Biomni skill format: front matter, when to use it, steps, quality bar and output conventions
category: General
when_to_use: The user wants to add a new skill, or to change an existing one, and wants it to follow the common format and quality standard
avoid: A skill must refer only to functions or software that really exist locally; do not invent interfaces; do not copy text from other platforms; label any step that has not been verified
uses: the local skills folder and its format rules
chain: Once a new skill is written, use the skill library's loading function to confirm that it can be read
---
## Steps
1. Front matter: title (short), description (one sentence), category, when_to_use, avoid, uses (functions or software that really exist), and chain (upstream and downstream).
2. Steps: write them in order. Each step has runnable code or a clear action. Say whether the software needed is available on this computer.
3. Quality bar: write at least three items, explaining the common mistakes and how to avoid them.
4. Output conventions: state the tables, figures, and the versions and dates to be recorded.
5. Verification: use the skill library's loading function to confirm that the file can be read and that all front matter fields are present.

## Quality bar
- Each function listed in uses must be importable locally (or be marked as needing installation).
- Do not write numbers or thresholds without a basis; state the source of each threshold.
- Steps that cannot be done on this computer must be clearly marked, so that the user does not think they can run.

## Output conventions
- The path of the new skill file, the result of the front-matter check, and the result of the loading test.
- State the revision date and a summary of the changes.
