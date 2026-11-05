---
title: Iterating computational methods with the TusoAI external API (requires an API key)
description: With a TusoAI external API key, use it for fast computational method iteration: evaluator consistency, resumable checkpoints, multi-machine search and history review
category: Data & workflows
when_to_use: The user has a TusoAI API key and wants several rounds of computational method optimisation, with resumable checkpoints
avoid: Cannot be used without an API key; confirm the data privacy of the external service first; each iteration needs clear evaluation metrics, and the evaluator must not be overfitted
uses: the TusoAI external interface; local checkpoints and logs use pandas and standard files
chain: Choose one of this and tusoskill: use this skill when you have a key, and tusoskill's local workflow when you do not
---
## Steps
1. Define the evaluator: fixed evaluation metrics and a test set, with the version stated.
2. Iterate: change only one thing per round, and record the change, the metrics and the checkpoint.
3. Checkpoints: save the state at the end of each round (parameters, results, logs), so that an interrupted run can resume from the checkpoint.
4. Multi-machine search: distribute candidates across machines, and collect the results into one log.
5. Review: check the history regularly to judge whether the method is overfitting the evaluator.

## Quality bar
- The evaluation metrics and the test set must not change during iteration, otherwise the results cannot be compared.
- Every change in each round must be traceable.
- Without a key, do not fabricate API results.

## Output conventions
- Table: round, change, metrics, checkpoint location.
- State the evaluator version, the number of iterations, the machines and the date.
