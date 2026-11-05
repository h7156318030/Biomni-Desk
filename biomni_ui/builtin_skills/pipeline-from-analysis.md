---
title: Turn an analysis into a reproducible pipeline (Nextflow)
description: Organise a completed analysis (a notebook, a session record or a script) into a reproducible Nextflow pipeline, with steps and configuration laid out in nf-core style
category: Data & workflows
when_to_use: The user wants to turn a finished analysis into a pipeline that can be run again, or wants someone else to rerun it on a server
avoid: Without Nextflow and a container runtime on this computer, only the pipeline code and documentation can be generated, not a full run here; the software version of every step must be fixed
uses: reads the analysis record and produces a Nextflow project layout; running it needs Nextflow with Docker or Conda
chain: Upstream is the completed analysis; downstream goes to pipeline-module-author (to add steps) and pipeline-hpc-validate (to validate)
---
## Steps
1. Read the analysis record: list the input, output, command and software version of each step.
2. Split into steps: each analysis action becomes one process, with inputs and outputs connected through channels.
3. Organise the project: main.nf, nextflow.config, modules/ and conf/, with parameters held in params.
4. Fix the versions: each process specifies a container or Conda environment with a version number.
5. Example data: provide a small test input, so that you can check that the pipeline runs end to end.

## Quality bar
- Pass all paths and the reference genome as parameters; do not hard-code them.
- Each process's outputs need a check (for example that the files exist and their line counts are correct).
- State whether it can run on this computer; if not, say so clearly.

## Output conventions
- A list of the project structure, a list of the main processes, and a description of the parameters.
- State the source of the original analysis, the software versions, the test input and the date.
