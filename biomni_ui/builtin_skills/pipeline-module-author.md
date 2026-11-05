---
title: Add a step to a Nextflow pipeline (the nf-core way)
description: Add a module to a pipeline following nf-core conventions: take an official module from the offline index, or create a new module scaffold, and write its tests
category: Data & workflows
when_to_use: The user wants to add an analysis step (such as alignment, quantification or annotation) to an existing pipeline, and wants it to follow the nf-core structure
avoid: Without the nf-core tools on this computer, only the module scaffold and documentation can be generated; module versions must be fixed; do not mix code from different sources in one module
uses: the nf-core module index, Nextflow
chain: Upstream is the project from pipeline-from-analysis; downstream goes to pipeline-hpc-validate
---
## Steps
1. Search: first look for an existing module in the nf-core module index (by tool name), and use it if found.
2. If none exists, create one: generate the module scaffold (main.nf, meta.yml, environment.yml, tests).
3. Write the process: the channel types of the inputs and outputs must match; output file names must include the sample identifier.
4. Write tests: assertions on the minimal test data (the outputs exist, and key fields are correct).
5. Connect to the pipeline: call the module in the workflow, and check how the channels are connected.

## Quality bar
- A module needs a version number and a container or environment file.
- Each module has a test that can run.
- Do not change the interface of an existing module unless you state the scope of the impact.

## Output conventions
- The module folder structure, the interface description (inputs and outputs), and the test description.
- State the tool version, the source (nf-core or newly created) and the date.
