---
type: concept
ingested: 2026-06-02
tags: [retrieval, graphrag, rrf, vector-search]
---

# Hybrid Retrieval (Vector + Graph)

A retrieval strategy that combines dense vector similarity search with graph traversal, typically fused using Reciprocal Rank Fusion (RRF), to achieve multi-granular matching for knowledge-grounded generation.

## Key idea

Instead of relying solely on either vector similarity (which misses structural relationships) or graph traversal (which misses semantic similarity), combine both:

1. **Vector search**: Dense embeddings for semantic similarity matching
2. **Graph traversal**: 1-hop neighbor exploration for structural relationship discovery
3. **RRF fusion**: Reciprocal Rank Fusion to merge ranked lists from both sources

## Architecture

- Separate embeddings maintained for entities, chunks, and relations
- Seed entity identification via noun phrase extraction + vector similarity
- 1-hop graph traversal from seed nodes
- Re-ranking via cosine similarity on relation/chunk embeddings
- RRF fusion for final ranking

## Sources

- [Towards Practical GraphRAG](../sources/efficient-kgc-rag.md): Proposed this hybrid approach for enterprise GraphRAG deployment
