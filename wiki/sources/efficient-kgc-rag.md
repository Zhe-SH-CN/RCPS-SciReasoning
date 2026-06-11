---
type: paper
date: 2025-07-04
ingested: 2026-06-02
status: read
raw: ../../raw/2025-01-congmin-towards-practical-graphrag-efficient-kno.pdf
arxiv: 2507.03226
tags: [graphrag, kg-construction, hybrid-retrieval, enterprise, dependency-parsing]
---

# Towards Practical GraphRAG: Efficient Knowledge Graph Construction and Hybrid Retrieval at Scale

> One-line summary: A scalable enterprise GraphRAG framework that uses dependency parsing for cost-efficient KG construction (94% of LLM-based performance) combined with hybrid vector+graph retrieval via RRF fusion.

## Key claims

- Dependency-based KG construction achieves 94% of LLM-based performance (61.87% vs. 65.83% weighted semantic alignment) while being orders of magnitude faster and cheaper. (§4.3.1)
- Hybrid retrieval combining vector similarity with graph traversal via RRF outperforms vanilla dense retrieval by up to 15% on context precision and improves answer completeness. (§4.3.1)
- The framework is the first application of GraphRAG to enterprise legacy code migration, demonstrating significant improvements over dense retrieval baselines. (§1, §4)
- Maintaining separate embeddings for entities, chunks, and relations enables multi-granular matching that improves retrieval quality. (§3.2.1)
- Both GraphRAG variants (GPT-4o and dependency) reduce no-coverage responses by 32% and increase full-coverage responses by at least 8%. (§4.3.1)

## Evidence quality / methodology

- Task: Knowledge graph construction and retrieval-augmented generation for enterprise legacy code migration
- Datasets: Two enterprise datasets — CCM Chat (code migration Q&A) and CCM Code Proposal (code migration proposals)
- Metrics: RAGAS (Context Precision, Answer Relevancy, Faithfulness), Semantic Alignment (No Cov./Partial Cov./Full Cov.), LLM-as-Judge (Winning Rate, Avg Score 1-5)
- Baselines: Dense vector retrieval (ada-002 embeddings)
- KG construction approaches: Dependency parsing (SpaCy) vs. GPT-4o LLM-based
- Retrieval: Hybrid RRF fusion of vector similarity + 1-hop graph traversal
- Infrastructure: Milvus (vector DB), iGraph (graph DB), OpenAI text-embedding-3-large

### Main results

| Method | Context Precision | Semantic Alignment (Weighted) |
|---|---|---|
| Dense Vector (ada-002) | 54.35% | 50.80% |
| GraphRAG (GPT-4o) | 63.82% | 65.83% |
| GraphRAG (Dependency) | 61.07% | 61.87% |

## How this relates to the wiki

- [GraphRAG](../concepts/graphrag.md): Extends the GraphRAG paradigm with cost-efficient construction and hybrid retrieval for enterprise deployment.
- [KG Construction](../concepts/kg-construction.md): Proposes dependency parsing as a practical alternative to LLM-based KG construction.
- [Hybrid Retrieval](../concepts/hybrid-retrieval.md): Introduces RRF-based fusion of vector similarity and graph traversal for multi-granular matching.
- [LightKGG](../sources/lightkgg.md): Both papers address efficient KG construction without LLM dependency; this paper focuses on enterprise GraphRAG deployment while LightKGG focuses on SLM-based extraction.

## Notable quotes

> "Careful engineering of classical NLP techniques can match modern LLM-based approaches while enabling practical, cost-effective, and domain-adaptable retrieval-augmented reasoning at scale." (§Abstract)

> "Dependency-based extraction achieves 94% of LLM-based performance while processing documents orders of magnitude faster and at significantly lower cost." (§3.1.2)

## Open questions

- How does the dependency-based approach perform on general-domain benchmarks (e.g., HotpotQA) beyond enterprise code migration?
- Can advanced graph traversal strategies beyond one-hop further improve retrieval quality?
- What is the cost breakdown comparison between dependency-based and LLM-based KG construction at enterprise scale?
