---
type: concept
ingested: 2026-06-02
tags: [kg-construction, hypergraph, hrkg]
---

# Hyper-Relational Knowledge Graph (HRKG)

An extension of traditional triple-based knowledge graphs that uses hyperedges to connect multiple nodes simultaneously, enabling more natural representation of complex multi-body relations with qualified/annotated information.

## Key differences from traditional KG

| Aspect | Traditional KG | HRKG |
|---|---|---|
| Basic unit | Triple (h, r, t) | Hyperedge connecting multiple nodes |
| Relations | Binary only | Multi-body relations |
| Qualifiers | Not supported | Supports additional context/qualifiers |
| Complexity | Simple | Handles many-to-many relations |

## Construction methods

- **GCLR** (Datta et al., 2024): LLM-based HRKG construction using prompt engineering and CoT with GPT-3.5
- **LLHKG** (Zhu et al., 2026): Lightweight LLM framework (LLaMA + Qwen) with extraction and correction modules

## Related concepts

- **Knowledge Hypergraph**: Further extension using hyperedges for large-scale complex knowledge modeling
- **HyperGraphRAG**: RAG system using hypergraph-structured knowledge representation

## Sources

- [LLHKG](../sources/llhkg.md): Survey and framework for HRKG construction using lightweight LLMs
