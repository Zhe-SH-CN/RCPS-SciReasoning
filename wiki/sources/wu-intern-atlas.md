---
type: paper
date: 2026-04-30
ingested: 2026-05-28
status: read
raw: ../../raw/2026-04-wu-intern-atlas-a-methodological-evolution.pdf
arxiv: 2604.28158
tags: [kg-construction, methodology-graph, llm, automated-science]
---

# Intern-Atlas: A Methodological Evolution Graph as Research Infrastructure for AI Scientists

> Builds a massive methodological evolution graph from 1M+ AI papers, tracing how research methods emerge, adapt, and build upon one another — a structured alternative to citation-based research infrastructure.

## Key claims

- Existing research infrastructure is document-centric (citations between papers) but lacks method-level evolutionary relationships. (§Introduction)
- Intern-Atlas constructs a graph with 9.4M semantically typed edges from 1,030,314 papers, grounding each edge in verbatim source evidence. (§Method)
- A self-guided temporal tree search algorithm constructs evolution chains tracing method progression over time. (§Method)
- The graph enables downstream applications in idea evaluation and automated idea generation. (§Experiments)

## Evidence quality / methodology

- Scale: 1,030,314 papers from AI conferences, journals, and arXiv preprints
- Output: 9,410,201 semantically typed edges with verbatim evidence
- Evaluation: compared against expert-curated ground-truth evolution chains
- Applications: idea evaluation and automated idea generation demos

## How this relates to the wiki

- Core contribution to KG construction: builds a knowledge graph specifically about research methodology evolution
- Relevant to LLM-based automated scientific discovery

## Open questions

- How does the method-level graph compare to citation graphs for downstream tasks?
- Can the evolution chain algorithm generalize beyond AI to other scientific domains?
- What are the failure modes when methods are renamed or split across papers?
