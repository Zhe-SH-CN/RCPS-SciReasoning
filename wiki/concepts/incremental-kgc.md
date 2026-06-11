---
type: concept
ingested: 2026-06-02
aliases: [incremental-knowledge-graph-construction, streaming-kgc]
---

# Incremental Knowledge Graph Construction

Incremental KGC refers to building knowledge graphs from streaming or continuously arriving data, rather than from a fixed corpus in a single batch. The key challenge is adding, modifying, and retiring knowledge while preserving graph consistency and avoiding expensive full reconstruction.

## Approaches

- **DIAL-KG** ([source](../sources/dial-kg.md)): Closed-loop framework with Meta-Knowledge Base for governance and schema evolution in streaming settings. Achieves SOTA on static and streaming benchmarks.
- **iText2KG** ([source](../sources/llm-empowered-kgc-survey.md)): Zero-shot incremental construction with user-defined blueprints; limited in discovering knowledge types beyond the blueprint scope.
- **EDC** ([source](../sources/methods-kgc-text.md)): Decomposes KGC into open IE → schema definition → normalization; single-batch and static architecture limits streaming applicability.

## Key challenges

- **Knowledge staleness:** Old facts must be deprecated or revised as new information arrives
- **Schema drift:** The ontology must evolve as new knowledge types emerge
- **Incremental consistency:** Updates must not introduce contradictions or orphaned entities
- **Scalability:** Processing cost must not grow linearly with total graph size
