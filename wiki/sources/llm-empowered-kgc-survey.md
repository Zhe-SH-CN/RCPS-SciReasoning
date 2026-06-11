---
type: paper
date: 2025-10-23
ingested: 2026-06-02
status: read
raw: ../../raw/2510.20345.pdf
arxiv: 2510.20345
tags: [survey, llm, kgc, ontology, extraction, fusion, schema-based, schema-free]
---

# LLM-empowered Knowledge Graph Construction: A Survey

> A comprehensive survey of how LLMs are transforming KG construction across ontology engineering, knowledge extraction, and knowledge fusion, analyzing both schema-based and schema-free paradigms.

## Key claims

- **LLMs reshape the classical three-layered KGC pipeline.** The survey systematically analyzes how LLMs transform ontology engineering, knowledge extraction, and knowledge fusion — shifting from rule-based pipelines to language-driven generative frameworks. (§1, §7)
- **Two complementary paradigms emerge.** Schema-based approaches (structure, normalization, consistency) vs. schema-free approaches (flexibility, adaptability, open discovery) represent the two principal methodological directions in LLM-driven KGC. (§4)
- **Three key trends across the pipeline.** (1) Evolution from static schemas to dynamic induction; (2) Integration of pipeline modularity into generative unification; (3) Transition from symbolic rigidity to semantic adaptability. (§7)
- **KGs are evolving from static repositories to dynamic cognitive infrastructure.** KGs increasingly serve as external knowledge memory for LLMs (RAG), dynamic memory for agentic systems, and reasoning substrates. (§6.2, §6.4)
- **Three future directions identified.** KG-based reasoning for LLMs, dynamic knowledge memory for agentic systems, and multimodal KG construction. (§6)

## Evidence quality / methodology

- **Task:** Survey / literature review of LLM-empowered KG construction
- **Scope:** Ontology engineering (§3), knowledge extraction (§4), knowledge fusion (§5), future directions (§6)
- **Coverage:** Traditional pre-LLM methods (§2), top-down ontology construction (§3.1), bottom-up schema construction (§3.2), schema-based extraction (§4.1), schema-free extraction (§4.2), schema-level fusion (§5.1), instance-level fusion (§5.2), hybrid fusion (§5.3)
- **Published:** ICAIS 2025 conference paper
- **Limitations:** As a survey, no original experiments; relies on synthesizing existing work

## How this relates to the wiki

- [Schema-free KGC](../concepts/schema-free-kgc.md): Survey provides comprehensive taxonomy of schema-free approaches including DIAL-KG, EDC, AutoKG, iText2KG
- [Schema-based KGC](../concepts/schema-based-kgc.md): Survey covers static and dynamic schema-based methods including SAC-KG, CoT-Ontology, KARMA, ODKE+
- [LLM-based KGC](../concepts/llm-based-kgc.md): Central topic — how LLMs transform knowledge extraction pipelines
- [Incremental KGC](../concepts/incremental-kgc.md): Discusses dynamic schema evolution and adaptive schema approaches (AdaKGC, AutoSchemaKG)
- [DIAL-KG](../sources/dial-kg.md): Survey contextualizes DIAL-KG within the broader schema-free paradigm
- [Knowledge fusion](../concepts/knowledge-fusion.md): Covers entity alignment, entity resolution, and knowledge integration

## Notable quotes

> "LLMs are evolving beyond traditional text-processing tools into cognitive engines that seamlessly bridge natural language and structured knowledge." (§1)

> "Together, these shifts redefine KGs as living, cognitive infrastructures that blend language understanding with structured reasoning." (§7)

## Open questions

- How to balance the trade-off between schema flexibility and quality guarantees in schema-free paradigms?
- Scalability of LLM-based KGC for web-scale corpora remains an open challenge — the survey identifies this but does not provide solutions.
- The relationship between KG-based reasoning and KG construction quality forms a "virtuous cycle" that is theorized but not yet well-studied empirically.
- Multimodal KG construction faces challenges in modality heterogeneity, alignment noise, and scalability under missing modalities.
