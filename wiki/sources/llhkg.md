---
type: paper
date: 2026-04-21
ingested: 2026-06-02
status: read
raw: ../../raw/2026-01-qiubai-construction-of-knowledge-graph-based-on.pdf
arxiv: 2604.19137
tags: [kg-construction, plm-survey, hyper-relational-kg, lightweight-llm]
---

# Construction of Knowledge Graph based on Language Model

> One-line summary: A comprehensive survey of PLM-based KG construction methods plus a novel Hyper-Relational Knowledge Graph (HRKG) framework (LLHKG) using lightweight LLMs that achieves GPT-3.5-level performance.

## Key claims

- PLM-based KG construction is a mainstream approach with significant advantages over traditional deep learning methods due to low labeled data requirements and strong generalization. (§1, §2)
- Lightweight LLMs (LLaMA 3.1:8B + Qwen 2.5:7B) can achieve HRKG construction performance comparable to GPT-3.5 (BERTScore F1: 0.53 vs. 0.53). (§4.4)
- The LLHKG framework decomposes HRKG construction into extraction and correction modules, using different lightweight models for each stage. (§4.1, §4.3)
- Knowledge mining based on LLMs can be categorized into prompt-based, zero/few-shot, and domain-specific approaches. (§2.2)
- Knowledge hypergraphs extend HRKG with hyperedges for large-scale complex knowledge modeling, showing potential in RAG systems. (§3)

## Evidence quality / methodology

- Task: Hyper-Relational Knowledge Graph (HRKG) construction from text
- Dataset: HyperRED (hyper-relational extraction benchmark)
- Metrics: BERTScore (Precision, Recall, F1)
- Baselines: GCLR (GPT-3.5-based HRKG construction)
- Models: LLaMA 3.1:8B (extraction), Qwen 2.5:7B (correction)
- Evaluation: BERTScore comparison showing lightweight LLMs match GPT-3.5

### Main results

| Framework | Model | Precision | Recall | F1 |
|---|---|---|---|---|
| GCLR | GPT-3.5 | 0.53 | 0.56 | 0.53 |
| LLHKG (Ours) | LLaMA 3.1:8B & Qwen 2.5:7B | 0.52 | 0.56 | 0.53 |

## How this relates to the wiki

- [KG Construction](../concepts/kg-construction.md): Comprehensive survey of PLM-based KG construction methods covering the full landscape.
- [LightKGG](../sources/lightkgg.md): Both papers demonstrate lightweight models can achieve competitive KG construction; LightKGG focuses on traditional KG while LLHKG focuses on HRKG.
- [LLM for KG](../concepts/llm-for-kg.md): Survey categorizes LLM-based KG construction into zero-shot, few-shot, domain-specific, and iterative validation approaches.
- [Hyper-Relational KG](../concepts/hyper-relational-kg.md): Introduces HRKG as an extension of traditional triple-based KGs for complex multi-body relations.

## Notable quotes

> "Under our framework, the KG construction capability of lightweight LLM is comparable to GPT3.5." (§Abstract)

> "HRKG addresses [the limitation of traditional KGs] by using hyperedges to connect multiple nodes simultaneously, more naturally representing complex multi-body relations." (§3)

## Open questions

- How does LLHKG scale to larger datasets beyond HyperRED?
- Can the extraction-correction pipeline be further optimized with end-to-end training?
- What are the trade-offs between HRKG and knowledge hypergraph representations for different application domains?
