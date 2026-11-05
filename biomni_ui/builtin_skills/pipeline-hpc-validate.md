---
title: HPC validation of a pipeline (pre-delivery checks)
description: Before handing a Nextflow pipeline to a platform, run local pre-checks (structure, configuration layers, platform-reserved configuration keys), then one controlled test run on HPC
category: Data & workflows
when_to_use: The user's pipeline is to be submitted to an HPC or platform, and they want problems found before delivery
avoid: The HPC test run needs platform permissions and resources; the pre-checks find only structural problems and cannot replace a real run result; do not change configuration keys reserved by the platform
uses: reads the pipeline folder and checks syntax and configuration; the HPC run needs the commands provided by the platform
chain: Upstream is the output of pipeline-from-analysis or pipeline-module-author
---
## Steps
1. Local pre-check: confirm the folder structure is complete (main.nf, nextflow.config, modules/, test inputs).
2. Configuration check: confirm that no platform-reserved configuration key has been overwritten, and that the default parameter values are reasonable.
3. Syntax check: Nextflow lint or dry run (needs a Nextflow environment; if Nextflow is not installed on this computer, do only a text check and say so).
4. HPC test run: run once with the smallest test data, and record the failed processes and their logs.
5. Bounded debugging: if it fails, change the pipeline at most twice, recording each change and its reason; if it still fails, report to the user.

## Quality bar
- Set a resource limit for the test run, so that it does not use too much.
- Save the failure logs and attach them to the report.
- An item that did not pass must never be reported as passed.

## Output conventions
- Table: check item, result (passed, failed, not tested), log location.
- State the pipeline version, the platform, the test data and the date.
