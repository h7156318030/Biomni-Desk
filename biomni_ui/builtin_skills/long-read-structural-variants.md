---
title: Structural variant calling from long reads (ONT, PacBio)
description: Call structural variants (deletions, insertions, inversions, translocations) from aligned long-read BAM files, merge and validate the results from two calling tools
category: Genomics & genetics
when_to_use: The user has ONT or PacBio long-read data and wants to call structural variants, or wants to compare two sets of calls
avoid: Needs a reference genome and substantial compute; short-read data is not suited to high-accuracy structural variant calling; the calls in hotspot regions must be checked by hand
uses: Sniffles2, cuteSV; samtools
chain: Upstream is the long-read alignment (minimap2 or ngmlr); downstream is functional annotation of the structural variants
---
## Steps
1. Check the alignment: the reference version matches the BAM, and record the coverage and the mapping rate.
2. Run two calling tools (for example Sniffles2 and cuteSV), each producing a VCF.
3. Merge: take the intersection of the two as the high-confidence set, and note the calls that appear in only one tool.
4. Normalise: standardise the variant representation (left-align, split nested events).
5. Check: view the known structural-variant hotspot regions by hand in IGV screenshots, to confirm them.

## Quality bar
- Events that appear in only one tool are less credible; flag them separately.
- Repetitive regions produce many false positive structural variants; use filtering rules there.
- For samples with coverage below 10×, the detection rate drops noticeably.

## Output conventions
- Table: event type, position, length, supporting read count, agreement between the two tools.
- State the reference version, the tool versions, the coverage and the date.
