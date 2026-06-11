---
type: concept
ingested: 2026-06-02
aliases: [mkb]
---

# Meta-Knowledge Base (MKB)

A Meta-Knowledge Base is a management core and evolving metadata repository introduced in DIAL-KG. It serves as both a governance hub and evolutionary memory for incremental KG construction.

## Components

- **Entity Profiles:** Structured, normalized descriptions of real-world entities, consolidating verified canonical names, aliases, and types. Serve as semantic anchors for coreference resolution.
- **Schema Proposals:** Candidate schemas induced from accumulated verified facts, categorized into:
  - **Relation Schemas:** Define static fact structures with domain/range constraints
  - **Event Schemas:** Define dynamic event structures with trigger and argument role constraints

## Role in pipeline

The MKB provides batch-aware contextual constraints for extraction, verification, and schema evolution. It enables the system to progressively form a self-evolving schema system without a fixed ontology. Retrieved schemas are injected into prompts as retrieval-augmented generation constraints.

## Related

- [DIAL-KG](../sources/dial-kg.md): Original paper introducing the MKB concept
