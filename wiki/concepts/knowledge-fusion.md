---
type: concept
ingested: 2026-06-02
aliases: [kg-fusion, entity-alignment, entity-resolution]
---

# Knowledge Fusion

Knowledge Fusion focuses on integrating heterogeneous knowledge sources into a coherent and consistent graph by resolving duplication, conflict, and heterogeneity. Core sub-tasks include entity alignment, entity resolution, and cross-source integration.

## Levels

- **Schema-level fusion:** Aligning ontological schemas across knowledge bases (e.g., schema matching, ontology alignment)
- **Instance-level fusion:** Resolving entity references across datasets (entity alignment, entity resolution, coreference resolution)
- **Hybrid frameworks:** Combining schema-level and instance-level fusion for comprehensive integration

## Traditional methods
- Lexical and structural similarity measures
- Embedding-based techniques in shared vector spaces
- Multi-feature fusion (structural + attribute + relational similarities)

## LLM-powered approaches
- LLMs enable semantic unification through natural language grounding
- Cross-lingual and cross-modal entity alignment
- Dynamic knowledge updating for evolving KGs

## Challenges
- Semantic heterogeneity across sources
- Large-scale integration scalability
- Dynamic knowledge updating without full reconstruction
- Noise and inconsistency in multi-source fusion

## Related

- [LLM-empowered KGC Survey](../sources/llm-empowered-kgc-survey.md): Comprehensive review of fusion techniques
- [Incremental KGC](../concepts/incremental-kgc.md): Incremental fusion as part of streaming KGC
