---
type: concept
ingested: 2026-06-02
aliases: [kg-reasoning, knowledge-graph-reasoning]
---

# KG-based Reasoning

KG-based reasoning uses knowledge graphs as structured representations to enhance LLM reasoning, planning, and decision-making. Instead of relying solely on LLM internal knowledge, structured KGs provide explicit, auditable, and queryable knowledge bases.

## Approaches

- **KGoT** ([source](../sources/kgot.md)): Dynamically constructs KGs for task-solving, enabling low-cost models to solve complex tasks. Uses dual-LLM architecture with Cypher/SPARQL/Python for KG querying.
- **GraphRAG** ([source](../sources/llm-empowered-kgc-survey.md)): Uses KGs as retrieval backbones for LLM generation.
- **CogER**: Cognition-aware KG reasoning for recommendations.
- **PKG-LLM**: Domain KGs for knowledge augmentation in biomedical applications.

## Benefits over pure LLM reasoning

- **Transparency:** Explicit knowledge representation enables auditability
- **Reduced hallucination:** KG-grounded responses are verifiable
- **Cost efficiency:** Small models can process structured KGs effectively
- **Composability:** KGs can be queried, merged, and evolved

## Challenges

- KG construction quality directly impacts reasoning quality
- Scaling to very large KGs while maintaining query efficiency
- Dynamic KG evolution during multi-step reasoning tasks

## Related

- [LLM-based KGC](../concepts/llm-based-kgc.md): LLMs as both KG constructors and reasoning engines
- [Incremental KGC](../concepts/incremental-kgc.md): Evolving KGs during task execution
- [KGoT](../sources/kgot.md): Primary example of KG-based reasoning for AI assistants
