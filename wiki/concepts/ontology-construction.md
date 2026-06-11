---
type: concept
ingested: 2026-06-02
tags: [ontology, enterprise-kg, semantic-modeling, llm]
---

# Ontology Construction for Enterprise KGs

The process of creating formal ontologies (RDF/OWL schemas) from unstructured enterprise data, defining classes, properties, hierarchies, and constraints for enterprise knowledge graphs.

## Pipeline stages

1. **Data Ingestion**: Parse unstructured documents, enforce structured output models (e.g., Pydantic)
2. **Ontological Element Extraction**: Identify core classes and properties from text using LLMs
3. **Hierarchy Construction (Entailment)**: Organize classes into logical taxonomies via LLM reasoning
4. **RDF Serialization**: Convert to standard RDF triples (owl:Class, owl:ObjectProperty)

## Challenges

- **Scope definition**: LLMs struggle to determine which classes/properties are relevant
- **Class vs. individual confusion**: LLMs sometimes propose individuals instead of classes
- **Hierarchy directionality**: Entailment phase can confuse subsumption direction
- **Benchmark gap**: Lack of comprehensive benchmarks for end-to-end ontology construction

## Sources

- [OntoEKG](../sources/ontodekg.md): LLM-driven pipeline for enterprise ontology construction
