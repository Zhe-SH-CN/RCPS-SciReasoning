---
type: paper
date: 2025-10-27
ingested: 2026-06-02
status: read
raw: ../../raw/2025-01-teng-lightkgg-simple-and-efficient-knowledge.pdf
arxiv: 2510.23341
tags: [kg-construction, small-language-models, efficient, topology]
---

# LightKGG: Simple and Efficient Knowledge Graph Generation from Textual Data

> One-line summary: A lightweight framework enabling KG extraction from text using small language models (SLMs) via context-integrated graph extraction and topology-enhanced relationship inference, achieving LLM-like accuracy at a fraction of the computational cost.

## Key claims

- SLMs can achieve competitive KG extraction performance (96-97% of KGGen's F1) when augmented with topology-based inference, challenging the assumption that LLMs are indispensable for high-quality KG generation. (§Abstract, §4.3)
- Context-integrated graph extraction unifies entities, edges, and contextual metadata into a single graph structure during extraction, eliminating the need for costly downstream semantic parsing. (§3.1)
- Topology-enhanced relation inference leverages structural graph features (node centrality, path density, degree) to discover implicit relationships without LLM-scale semantic reasoning. (§3.3)
- Context integration is the most critical component; removing it causes 13.2% Relation-F1 drop and 15.6% MINE-score decline. (§4.4)
- LightKGG(DeepSeek-1.5B) even outperforms GraphRAG(GPT-4o) in MINE scores (0.567 vs. 0.501), showing topology can compensate for model scale limitations. (§4.3)

## Evidence quality / methodology

- Task: Knowledge graph extraction from text
- Datasets: SciERC (subset of 100 sentences, scientific entity/relation extraction) and MINE (knowledge graph quality evaluation)
- Metrics: Entity-F1, Relation-F1, MINE-scores
- Baselines: KGGen (GPT-4o), GraphRAG (GPT-4o), OpenIE
- Models tested: Phi-3.5-mini-instruct (SLM), GLM-Edge-1.5B-Chat (SLM), DeepSeek-R1-Distill-Qwen-1.5B (SLM), GPT-4o (LLM)
- Hardware: Single NVIDIA RTX4090 (24GB VRAM)
- Ablation study validates context integration and topology-enhanced inference as key components

### Main results

| Configuration | Entity-F1 | Relation-F1 | MINE-scores |
|---|---|---|---|
| KGGen (GPT-4o) | 0.891 | 0.853 | 0.685 |
| GraphRAG (GPT-4o) | 0.826 | 0.798 | 0.501 |
| OpenIE | 0.685 | 0.721 | — |
| LightKGG (Phi) | 0.856 | 0.831 | 0.673 |
| LightKGG (GLM) | 0.832 | 0.732 | 0.568 |
| LightKGG (DeepSeek) | 0.788 | 0.717 | 0.567 |

## How this relates to the wiki

- [KG Construction](../concepts/kg-construction.md): Directly addresses the core problem of efficient KG construction from text.
- [LLM for KG](../concepts/llm-for-kg.md): Challenges the prevailing paradigm that LLMs are necessary for high-quality KG generation.
- [GraphRAG](../concepts/graphrag.md): Compares against GraphRAG as an LLM-driven baseline, showing SLM+topology can be competitive.
- [KGGen](../concepts/kggen.md): Primary LLM-driven baseline; LightKGG achieves 96-97% of its accuracy.

## Notable quotes

> "This work bridges the gap between automated knowledge extraction and practical deployment scenarios while introducing scientifically rigorous methods for optimizing SLM efficiency in structured NLP tasks." (§Abstract)

> "LightKGG demonstrates that SLMs + graph topology can rival LLM-driven KG extraction in accuracy while being vastly more efficient." (§4.5)

## Open questions

- How does LightKGG perform on non-English and multimodal data? The paper acknowledges this as future work.
- The paper only uses 100-sentence subsets for evaluation; scalability to larger corpora remains untested.
- Can domain-specific SLM fine-tuning close the remaining gap with LLMs for nuanced relationship types (e.g., "inhibits" vs. "regulates")?
