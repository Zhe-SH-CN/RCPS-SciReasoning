---
type: paper
date: 2026-05-06
ingested: 2026-06-02
status: read
raw: ../../raw/2605.05476.pdf
arxiv: 2605.05476
tags: [knowledge-graph, benchmark, GNN, evaluation, biomedical]
---

# A Unified Benchmark for Evaluating Knowledge Graph Construction Methods and Graph Neural Networks

> One-line summary: Introduces a dual-purpose benchmark that jointly evaluates GNN performance on noisy, text-derived graphs and the effectiveness of graph construction methods on downstream tasks, using biomedical KGs from a single textual corpus with expert-curated reference graphs.

## Key claims

- KGs automatically constructed from text suffer from inherent noise, fragmentation, and semantic inconsistencies that significantly affect GNN performance on downstream tasks, but it's often unclear whether observed results stem from the learning model or the quality of the constructed graph. (§1)
- A dual-purpose benchmark is needed to jointly evaluate (i) GNN robustness on noisy graphs and (ii) graph construction method effectiveness on downstream tasks. (§1)
- The benchmark is built in the biomedical domain from a single textual corpus, including two automatically constructed graphs plus a high-quality expert-curated reference graph serving as an upper performance bound. (§3)
- Semi-supervised node classification is used as the primary downstream task for controlled comparison. (§4)
- A standardized, reproducible, and extensible evaluation framework is provided to facilitate integration of new graph extraction methods and learning models. (§5)

## Evidence quality / methodology

- Task: Semi-supervised node classification on text-derived biomedical KGs
- Datasets: MedMentions (biomedical corpus), UMLS (expert-curated reference graph), two auto-extracted graphs (iText2KG, KGGen)
- Metrics: Micro-F1, Macro-F1 for node classification
- Baselines: GCN, GAT, GraphSAGE, TransGCN on various graph qualities
- Main results: Expert-curated graphs consistently outperform auto-extracted ones; GNN performance varies significantly across graph construction methods; the benchmark enables controlled comparison

## How this relates to the wiki

- [SciAtlas](../sources/qiao-sciatlas.md): Provides a standardized evaluation methodology applicable to large-scale KGs like SciAtlas
- [AutoSchemaKG](../sources/bai-autoschemakg.md): The benchmark methodology could evaluate AutoSchemaKG's schema-free construction approach
- [SynthKG](../sources/luo-synthkg.md): Directly relevant — SynthKG's construction quality could be evaluated using this benchmark framework

## Notable quotes

> "It is often unclear whether observed results stem from the learning model or from the quality of the constructed graph itself."

> "This design enables controlled comparison of construction methods and systematic evaluation of GNN robustness through semi-supervised node classification."

## Open questions

- Can this benchmark framework be extended to other domains beyond biomedical (e.g., scientific literature, financial knowledge)?
- How would the benchmark perform with newer GNN architectures or pre-training approaches?
- What is the relationship between graph construction quality metrics and downstream task performance?
