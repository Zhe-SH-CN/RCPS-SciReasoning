---
type: paper
date: 2026-03-26
ingested: 2026-06-02
status: read
raw: ../../raw/2603.25862.pdf
arxiv: 2603.25862
tags: [thesis, kg-construction, nlp, llm, open-ie, biomedical, domain-specific]
---

# Methods for Knowledge Graph Construction from Text Collections: Development and Applications

> A PhD thesis experimenting with NLP, ML, and Generative AI methods — powered by Semantic Web best practices — for automatic KG construction from large text corpora across three use cases: digital transformation monitoring, AECO research mapping, and biomedical causal relation extraction.

## Key claims

- **Unsupervised open-domain KG generation from micro-blogging text.** An optimized IE pipeline generates open-domain KGs without a target domain ontology schema, achieving ~12% entity linking to DBpedia and outperforming state-of-the-art methods. (§3, §6.1)
- **LLM-powered domain adaptation with minimal annotation.** Instruction-tuned LLMs enable customizing an existing IE pipeline to out-of-domain data (AECO research papers) with minimal annotation effort, leveraging few-shot learning and prompt chaining. (§4, §6.1)
- **Causal relation extraction from biomedical text using LLMs.** Instruction fine-tuned models achieve strong performance on detecting causal relations from multi-type entities in biomedical text; domain-specific pretraining enhances capabilities. (§5, §6.1)
- **End-to-end pipeline for drug-condition causal KGs.** A pipeline for constructing KGs of drug-condition causal relationships from patient-authored drug reviews, deploying an LLM trained on MIMICause with off-the-shelf entity linking. (§5.7, §6.1)
- **Topic-aware KG generation improves trend analysis.** Upstream topic modeling (optimized BERTopic) makes fine-grained research trend analysis more sensitive to low signals that wouldn't emerge at the full collection level. (§4.4, §6.1)

## Evidence quality / methodology

- **Task:** Knowledge graph construction from text across three domains
- **Use Cases:**
  - Digital Transformation monitoring from social media (tweets) and news
  - AECO (Architecture, Engineering, Construction, Operations) research landscape mapping
  - Biomedical causal relation extraction from EHRs and drug reviews
- **Methods:** Open IE, BiLSTM-CRF for NER, CNN for relation classification, LLMs (GPT-4, instruction-tuned models), BERTopic for topic modeling, Semantic Web (RDF, DBpedia linking)
- **Datasets:** Tweet collections, news corpora, SciERC AECO dataset, MIMICause, Adverse Drug Event dataset, Drug Review dataset
- **Evaluation:** Precision/Recall/F1 for IE; benchmark comparisons for LLM methods
- **Key results:** ~12% entity linking for social media KGs; LLMs outperform baselines on causal RE; domain-specific pretraining improves biomedical performance

## How this relates to the wiki

- [LLM-based KGC](../concepts/llm-based-kgc.md): Demonstrates practical LLM applications for KGC including few-shot, prompt chaining, and instruction fine-tuning
- [Schema-free KGC](../concepts/schema-free-kgc.md): The DT monitoring pipeline is fully unsupervised and schema-free
- [Knowledge fusion](../concepts/knowledge-fusion.md): Entity linking to DBpedia as a fusion step
- [LLM-empowered KGC Survey](../sources/llm-empowered-kgc-survey.md): This thesis provides practical implementations of methods discussed in the survey
- [Incremental KGC](../concepts/incremental-kgc.md): Linear scalability demonstrated with growing document sets

## Notable quotes

> "The increasing availability of unstructured data in natural language has opened unprecedented opportunities for automatic KG generation systems to extract complex knowledge structures and support actionable data analysis services for a wide range of domains." (§6.1)

> "Leveraging deep text understanding abilities of instruction-tuned LLMs enables to customize an existing Information Extraction pipeline to out-of-domain data, with minimal annotation effort." (§6.1)

## Open questions

- How to generalize the causal relation extraction pipeline across more diverse biomedical text types beyond clinical notes, case reports, and drug reviews?
- The entity linking rates (~8-12% to DBpedia) suggest significant room for improvement in cross-dataset entity resolution.
- Can the topic-aware KG generation approach scale to real-time streaming data for continuous monitoring?
