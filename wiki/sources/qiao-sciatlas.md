---
type: paper
date: 2026-05-20
ingested: 2026-06-02
status: read
raw: ../../raw/2026-01-shuofei-sciatlas-a-large-scale-knowledge-graph-f.pdf
arxiv: 2605.22878
tags: [knowledge-graph, scientific-retrieval, neuro-symbolic, large-scale-KG]
---

# SciAtlas: A Large-Scale Knowledge Graph for Automated Scientific Research

> One-line summary: SciAtlas is a large-scale, multi-disciplinary academic KG with 43M papers, 157M entities, and 3B triplets, designed as a panoramic scientific evolution network to empower AI agents with structured topological reasoning over academic knowledge.

## Key claims

- Current academic retrieval tools rely on superficial keyword matching or vector-space semantic retrieval, lacking topological reasoning capabilities needed to navigate complex logical connections across disciplines. (§Introduction)
- SciAtlas integrates over 43M papers from 26 disciplines with 157M entities and 3B triplets, providing a structured topological cognitive substrate that dismantles disciplinary barriers. (§2)
- A neuro-symbolic retrieval algorithm featuring tri-path collaborative recall and graph reranking achieves seamless transition from simple semantic matching to deterministic association discovery. (§3)
- SciAtlas supports multiple application directions: literature review, automated research trend synthesis, idea positioning, and academic trajectory exploration. (§4-6)
- Significantly reduces reasoning costs compared to agentic deep-research frameworks that are prone to logical hallucinations. (§4)

## Evidence quality / methodology

- Task: Multi-disciplinary scientific knowledge graph construction and retrieval
- Datasets: 43M papers from 26 disciplines (via OpenAlex)
- Metrics: Retrieval quality on downstream scientific tasks
- Baselines: Keyword-based retrieval, vector-space semantic retrieval, agentic deep-research frameworks
- Main results: SciAtlas provides structured topological reasoning that outperforms keyword and semantic-only approaches; open-sourced interfaces for KG retrieval

## How this relates to the wiki

- [AutoSchemaKG](../sources/bai-autoschemakg.md): Both build large-scale KGs from web-scale corpora, but SciAtlas focuses on academic literature while AutoSchemaKG targets general web documents
- [SynthKG](../sources/luo-synthkg.md): SciAtlas uses LLM-based extraction for academic KGs; SynthKG focuses on synthetic data generation for distilling KG extraction capabilities
- [KGC Benchmark](../sources/unified-kgc-benchmark.md): SciAtlas is an example of a large-scale constructed KG that could benefit from standardized evaluation

## Notable quotes

> "SciAtlas provides a structured topological cognitive substrate that dismantles disciplinary barriers and furnishes AI agents with a global perspective."

> "We develop a neuro-symbolic retrieval algorithm featuring tri-path collaborative recall and graph reranking, achieving a seamless transition from simple semantic matching to deterministic association discovery."

## Open questions

- How does SciAtlas handle evolving scientific fields where the knowledge graph needs continuous updates?
- What are the limitations of the tri-path collaborative recall when dealing with highly niche or emerging interdisciplinary topics?
- Can the neuro-symbolic approach be generalized to non-academic knowledge domains?
