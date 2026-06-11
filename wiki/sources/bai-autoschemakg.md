---
type: paper
date: 2025-05-29
ingested: 2026-06-02
status: read
raw: ../../raw/2025-01-jiaxin-autoschemakg-autonomous-knowledge-graph.pdf
arxiv: 2505.23628
tags: [knowledge-graph, schema-induction, LLM, event-extraction, conceptualization]
---

# AutoSchemaKG: Autonomous Knowledge Graph Construction through Dynamic Schema Induction from Web-Scale Corpora

> One-line summary: AutoSchemaKG eliminates the need for predefined schemas by using LLMs to simultaneously extract knowledge triples and induce comprehensive schemas directly from text, producing ATLAS — a family of KGs with 900M+ nodes and 5.9B edges from 50M+ documents.

## Key claims

- Existing KG construction methods require predefined schemas, limiting their ability to capture the full range of knowledge in web-scale corpora. (§Introduction)
- AutoSchemaKG leverages LLMs to simultaneously extract knowledge triples and induce schemas, modeling both entities and events while employing conceptualization to organize instances into semantic categories. (§3)
- Processing over 50 million documents, the system constructs ATLAS with 900M+ nodes and 5.9B edges — demonstrating scalability of schema-free KG construction. (§5)
- Schema induction achieves 92% semantic alignment with human-crafted schemas with zero manual intervention. (§5)
- The resulting KG outperforms state-of-the-art baselines on multi-hop QA tasks and enhances LLM factuality. (§5-6)

## Evidence quality / methodology

- Task: Autonomous KG construction + multi-hop QA + LLM factuality enhancement
- Datasets: 50M+ documents (web-scale), evaluated on HotpotQA, Musique, and custom factuality benchmarks
- Metrics: F1, EM for QA; BERTScore for schema alignment; factual accuracy for LLM evaluation
- Baselines: State-of-the-art KG construction methods; existing KGs (e.g., Freebase-derived)
- Main results: 92% schema alignment with human schemas; SOTA on multi-hop QA; improved LLM factuality

## How this relates to the wiki

- [SciAtlas](../sources/qiao-sciatlas.md): Both build large-scale KGs, but AutoSchemaKG uses dynamic schema induction while SciAtlas focuses on structured academic knowledge
- [SynthKG](../sources/luo-synthkg.md): Both use LLMs for KG construction, but AutoSchemaKG induces schemas while SynthKG generates synthetic training data
- [KGC Benchmark](../sources/unified-kgc-benchmark.md): AutoSchemaKG's approach could be evaluated using standardized benchmarks

## Notable quotes

> "Our schema induction achieves 92% semantic alignment with human-crafted schemas with zero manual intervention."

> "Billion-scale knowledge graphs with dynamically induced schemas can effectively complement parametric knowledge in large language models."

## Open questions

- How does the quality of schema induction degrade with more diverse or domain-specific corpora?
- What is the computational cost of the full AutoSchemaKG pipeline compared to schema-guided approaches?
- Can the induced schemas be refined iteratively as more documents are processed?
