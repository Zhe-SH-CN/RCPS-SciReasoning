---
type: paper
date: 2025-04-03
ingested: 2026-06-02
status: read
raw: ../../raw/2504.02670.pdf
arxiv: 2504.02670
tags: [kg-reasoning, ai-assistant, llm-agents, tool-use, dynamic-kg, cost-efficiency]
---

# Affordable AI Assistants with Knowledge Graph of Thoughts (KGoT)

> An innovative AI assistant architecture that integrates LLM reasoning with dynamically constructed knowledge graphs, enabling low-cost models to solve complex tasks effectively while reducing operational costs by 36× compared to GPT-4o.

## Key claims

- **KGoT transforms unstructured task data into structured KG representations.** The core innovation is encoding task-relevant knowledge as a dynamic knowledge graph that evolves iteratively through tool use, enabling small models to process complex tasks efficiently. (§1, §2.2)
- **29% improvement over GPT-4o mini baselines on GAIA.** KGoT with GPT-4o mini solves >2× more tasks than Hugging Face Agents with GPT-4o or GPT-4o mini on the GAIA benchmark. (§1, §5)
- **36× cost reduction compared to GPT-4o.** Operational costs drop from ~$187 (GPT-4o) to ~$5 (GPT-4o mini) while maintaining or improving performance. (§1, §5)
- **KG externalization reduces bias and noise.** By converting LLM thoughts and tool outputs into explicit triples, KGoT fosters transparency and enables quality checking of information before integration. (§2.5)
- **Dual-LLM architecture with modular tools.** A Graph Executor handles KG evolution while a Tool Executor manages tool selection; the system supports Cypher, SPARQL, and Python for KG querying. (§3.2)

## Evidence quality / methodology

- **Task:** Complex multi-step reasoning tasks (GAIA benchmark, SimpleQA)
- **Benchmarks:** GAIA (web navigation, code execution, image reasoning, scientific QA, multimodal), SimpleQA
- **Baselines:** Hugging Face Agents (GPT-4o, GPT-4o mini), other top GAIA leaderboard entries
- **Models tested:** GPT-4o mini, Qwen2.5-32B, Deepseek-R1-70B
- **Metrics:** Task success rate, operational cost (API tokens), latency
- **Main results:** 29%+ improvement over HF Agents on GAIA; 36× cost reduction; generalizes to other models and benchmarks
- **Implementation:** Open-source (https://github.com/spcl/knowledge-graph-of-thoughts)

## How this relates to the wiki

- [KG-based reasoning](../concepts/kg-based-reasoning.md): KGoT is a prime example of using KGs to enhance LLM reasoning through structured knowledge representation
- [LLM-based KGC](../concepts/llm-based-kgc.md): Uses LLMs as both KG constructors (Graph Executor) and tool managers (Tool Executor)
- [Incremental KGC](../concepts/incremental-kgc.md): KG evolves iteratively as new information is gathered — a form of incremental construction for task-solving
- [DIAL-KG](../sources/dial-kg.md): Both use dynamic KGs but for different purposes — DIAL-KG for persistent KG construction, KGoT for task-specific reasoning
- [LLM-empowered KGC Survey](../sources/llm-empowered-kgc-survey.md): KGoT represents the "KGs for LLMs" paradigm discussed in the survey

## Notable quotes

> "KGoT 'turns the unstructured into the structured', i.e., KGoT turns the often unstructured data such as website contents or PDF files into structured KG triples." (§1)

> "KGoT externalizes and structures the reasoning process, which reduces noise, mitigates model bias, and improves fairness." (§2.5)

## Open questions

- How does KGoT scale to tasks requiring very large knowledge graphs that exceed context window limits even with graph queries?
- The current tool suite is limited (web crawler, math solver, Python scripts) — how would the architecture handle more complex tool chains (e.g., multi-step API calls)?
- Can KGoT's KG-based approach be combined with existing KG construction methods (like DIAL-KG) to create persistent knowledge that accumulates across tasks?
