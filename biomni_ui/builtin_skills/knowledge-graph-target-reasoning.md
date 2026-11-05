---
title: Target reasoning on a knowledge graph (multi-hop associations)
description: Rank candidate targets starting from a disease, using multi-hop association or random walks on a biomedical knowledge graph, and give the reasoning paths as evidence
category: Drug discovery & safety
when_to_use: The user asks which targets are possible starting from a disease, and wants an explanation with several evidence paths, not just a single association score
avoid: The edges of a knowledge graph come from different sources and vary in quality; many paths do not make the paths credible; a graph data file is needed (this computer currently has only a small amount of data)
uses: graph data, networkx, dbtools.open_targets as a cross-check
chain: Upstream is the disease name; downstream goes to target-tractability-druggability
---
## Steps
1. Get the graph: download a public biomedical knowledge graph (nodes are genes, diseases and drugs; edges are associations), or build a small graph from open_targets associations as a substitute.
2. Seed nodes: start a personalised random walk from the disease node (restart probability about 0.3), and obtain each gene's visiting probability.
3. Evidence paths: for the top 20 genes, find the shortest path from the disease to the gene (at most 3 hops), and list the intermediate nodes and the edge types.
4. Cross-check against the open_targets results, and mark the candidates that appear in both.

## Quality bar
- Random walks favour highly connected nodes; correct for node degree.
- Check the source of each edge on a path; do not treat low-quality text-mining edges as experimental evidence.
- Record the graph version and build date.

## Output conventions
- Table: gene, walk score, evidence path, agreement with open_targets.
- State the graph source, the number of nodes and edges, the walk parameters and the date.
