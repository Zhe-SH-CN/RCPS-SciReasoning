---
type: paper
date: 2024-10-22
ingested: 2026-06-02
status: read
raw: ../../raw/2024-01-kumar-scaling-knowledge-graph-construction-thr.pdf
arxiv: 2410.16597
tags: [knowledge-graph, synthetic-data, distillation, RAG, document-level-KG]
---

# SynthKG: Scaling Knowledge Graph Construction through Synthetic Data Generation and Distillation

> One-line summary: SynthKG introduces a multi-step data synthesis pipeline for generating high-quality document-KG pairs, then distills this capability into a smaller LLM (Distill-SynthKG) that outperforms models up to 8x larger in KG quality, plus a novel graph-based retrieval framework for RAG.

## Key claims

- Document-level KG construction faces a fundamental scaling challenge: existing methods either rely on expensive LLMs (economically nonviable) or smaller models that produce incomplete/inconsistent graphs. (§1)
- The limitation stems not from model capabilities but from insufficient training on high-quality document-level KG data. (§1)
- SynthKG generates high-quality document-KG pairs through systematic chunking, decontextualization, and structured extraction using LLMs. (§3)
- Distill-SynthKG (a smaller fine-tuned model) surpasses all baseline models in KG quality, including models up to 8x larger. (§5)
- A novel graph-based retrieval framework for RAG outperforms all KG-retrieval methods across multiple benchmark datasets. (§5)

## Evidence quality / methodology

- Task: Document-level KG construction + KG-enhanced RAG
- Datasets: IndustryCorpus (synthetic training), DocRED (evaluation), HotpotQA, Musique, 2WikiMultiHopQA (RAG benchmarks)
- Metrics: ROUGE for KG quality; F1, EM for QA tasks; retrieval metrics
- Baselines: GPT-4o, LLaMA-3 (8B/70B), various KG construction methods, HippoRAG, GraphReader
- Main results: Distill-SynthKG outperforms all baselines on KG quality; graph retrieval framework achieves SOTA on multi-hop QA benchmarks

## How this relates to the wiki

- [AutoSchemaKG](../sources/bai-autoschemakg.md): Both use LLMs for KG construction, but SynthKG focuses on data synthesis and distillation while AutoSchemaKG focuses on schema induction
- [SciAtlas](../sources/qiao-sciatlas.md): SynthKG's distillation approach could potentially be applied to scale scientific KG construction like SciAtlas
- [KGC Benchmark](../sources/unified-kgc-benchmark.md): SynthKG's constructed KGs could serve as inputs to the benchmark's evaluation framework

## Notable quotes

> "This limitation stems not from model capabilities but from insufficient training on high-quality document-level KG data."

> "Distill-SynthKG not only surpasses all baseline models in KG quality (including models up to eight times larger) but also consistently improves in retrieval and question-answering tasks."

## Open questions

- How does the quality of synthetic training data affect the distilled model's generalization to different domains?
- Can the SynthKG pipeline be extended to handle multi-lingual documents?
- What are the trade-offs between the multi-step synthesis pipeline complexity and the final KG quality?
