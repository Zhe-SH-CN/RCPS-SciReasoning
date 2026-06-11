---
type: paper
date: 2026-02-01
ingested: 2026-06-02
status: read
raw: ../../raw/2026-01-abdulsobur-llm-driven-ontology-construction-for-ent.pdf
arxiv: 2602.01276
tags: [ontology-construction, enterprise-kg, llm, rdf, semantic-modeling]
---

# LLM-Driven Ontology Construction for Enterprise Knowledge Graphs

> One-line summary: OntoEKG is an LLM-driven pipeline that decomposes ontology construction into extraction and entailment modules, generating RDF ontologies from unstructured enterprise data with fuzzy-match F1 up to 0.724.

## Key claims

- Ontology construction for enterprise knowledge graphs remains largely manual and resource-intensive; LLM-driven pipelines can significantly accelerate this process. (§1)
- Decomposing ontology construction into extraction (classes + properties) and entailment (hierarchy reasoning) phases enables a structured, two-step LLM pipeline. (§3B)
- Fuzzy-match F1 of 0.724 in the Data domain demonstrates feasibility, but Finance (0.121) and Logistics (0.431) reveal limitations in scope definition and hierarchical reasoning. (§4B)
- There is a significant lack of comprehensive benchmarks for end-to-end ontology construction from unstructured text; existing benchmarks (OntoURL, LLMs4OL) are insufficient. (§4A)
- LLMs struggle with determining optimal model scope, distinguishing classes from individuals, and maintaining consistent hierarchy directionality in entailment. (§4B)

## Evidence quality / methodology

- Task: End-to-end ontology construction from unstructured enterprise text
- Datasets: Custom dataset across three enterprise sectors — Data, Finance, Logistics (internal policy documents)
- Metrics: Exact match F1, Fuzzy match F1 (embedding-based similarity threshold 0.94-0.95)
- Models: Google Gemini 3 Flash (extraction), Anthropic Claude 4.5 Opus (entailment)
- Output: RDF ontologies using owl:Class and owl:ObjectProperty
- Infrastructure: Google Colab, rdflib for RDF serialization

### Main results

| Use Case | Exact F1 | Fuzzy F1 |
|---|---|---|
| Data | 0.102 | 0.724 |
| Finance | 0.000 | 0.121 |
| Logistics | 0.048 | 0.431 |

## How this relates to the wiki

- [KG Construction](../concepts/kg-construction.md): Addresses the ontology/schema layer of KG construction, complementing entity/relation extraction approaches.
- [LLM for KG](../concepts/llm-for-kg.md): Demonstrates LLM-driven pipeline specifically for enterprise ontology generation.
- [LightKGG](../sources/lightkgg.md): LightKGG focuses on entity/relation extraction while OntoEKG focuses on the ontological schema layer; both use LLMs but at different stages.
- [Enterprise KG](../concepts/enterprise-kg.md): Directly addresses enterprise knowledge graph construction challenges.

## Notable quotes

> "Enterprise Knowledge Graphs have become essential for unifying heterogeneous data and enforcing semantic governance." (§I)

> "The best performances were reached in the Data use case, where we had an F1-score of 0.724 in the fuzzy setting." (§IVB)

## Open questions

- How can the extraction and entailment modules be improved to handle more complex enterprise domains (Finance, Logistics)?
- Can the pipeline be extended to handle named individuals and entity metadata extraction?
- What would a comprehensive benchmark for end-to-end ontology construction from unstructured data look like?
- How does progressive ontology construction (feeding existing models back into the pipeline) affect consistency across documents?
