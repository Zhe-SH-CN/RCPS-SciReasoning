# Deep Research: Sci-Reasoning Follow-up Work

Date: 2026-06-12

NotebookLM notebook:

- title: Sci-Reasoning
- id: `3804ed7f-ea19-47c0-8ac6-0f574d940862`
- url: https://notebooklm.google.com/notebook/3804ed7f-ea19-47c0-8ac6-0f574d940862

NotebookLM research task:

- task id: `2fe860fb-f999-4804-9c9a-1ea878d1433a`
- query: `Sci-Reasoning benchmark scientific idea generation Hit@10 improvements analysis derivative work related papers after release`
- mode: deep
- source: web

## Local Baseline Idea

See `research/current_acml_idea_2026-06-12.md`.

## NotebookLM MCP Status

The NotebookLM MCP server is installed at `/Users/zhe/.local/bin/notebooklm-mcp`.

Current Codex tool discovery did not expose a first-class `notebooklm` namespace, so this run invoked the installed MCP package directly through its Python entrypoints. Authentication tokens were present and NotebookLM API access succeeded after network escalation.

## Findings

NotebookLM deep research completed and 24 curated sources were imported. Five extra sources from web search were manually added:

- Graph2Idea: https://arxiv.org/abs/2606.09105
- FlowPIE: https://arxiv.org/abs/2603.29557
- LLM Jaggedness / SciAidanBench: https://arxiv.org/abs/2605.10574
- RQ-Bench / LLM-as-judge novelty limits: https://arxiv.org/abs/2606.12071
- Human study of LLM research ideas: https://arxiv.org/abs/2409.04109

### Direct Sci-Reasoning Context

Sci-Reasoning defines the key task we care about: given predecessor papers, predict target-paper-like ideas under Hit@10. Its own framing emphasizes innovation-pattern taxonomies, especially gap-driven reframing, cross-domain synthesis, representation shift, and their combinations.

NotebookLM also found secondary explainers and dataset mirrors:

- Emergent Mind overview.
- Hugging Face paper/dataset pages.
- Orchestra article explaining the dataset story.

These are useful for related-work wording, but the primary source remains the arXiv paper and local dataset.

### Follow-up and Adjacent Work

The relevant external work clusters into five groups:

1. **Future-aligned proposal prediction.** "Learning to Predict Future-Aligned Research Proposals with Language Models" reframes scientific ideation as time-sliced future alignment and uses Future Alignment Score rather than Sci-Reasoning Hit@10 alone.
2. **Structured context and graphs.** Graph2Idea argues that flat retrieved literature is noisy and weak at exposing cross-paper relations. It uses graph-structured contexts and reports gains on novelty, quality, and feasibility.
3. **Test-time search and evolution.** FlowPIE, Nova, and related search frameworks use iterative search, planning, crossover, mutation, or reward-guided evolution to expand idea space beyond one-shot prompting.
4. **Controllable generation.** LDC and SCI-IDEA focus on balancing novelty, feasibility, excitement, and effectiveness through learned control, embeddings, or structured facets.
5. **Evaluation and judge risk.** RQ-Bench and the large-scale human study warn that LLM judges can overrate model-generated novelty and that self-evaluation/diversity failures are central risks.

Additional adjacent agent benchmarks such as SciAgentGym, EXP-Bench, and Arbor are useful for automation framing, but they are broader agent-execution work rather than direct Sci-Reasoning Hit@10 improvements.

## Comparison Against BCS

Original BCS is a static generate-score-select pipeline:

- generate a larger target-hidden candidate pool,
- score candidates,
- select exactly 10,
- judge against hidden target after selection.

Compared with external work:

| External direction | What it does | Difference from BCS | What to borrow |
|---|---|---|---|
| Graph2Idea | Structures literature into graph-derived contexts | BCS currently uses mostly flat predecessor summaries | Add lightweight structured predecessor triples without building a full graph database |
| FlowPIE | Evolves ideas with search, crossover, mutation, reward | BCS currently expands candidates in one shot | Add a cheap crossover/mutation candidate-generation variant |
| Nova | Iterative planning/search to improve novelty/diversity | BCS lacks iterative planning | Add a bounded second-pass revision or mutation stage only if Phase 2 budget allows |
| LDC | Learns controllable novelty/feasibility/effectiveness rewards | Too heavy for the current deadline | Borrow only the multi-objective reporting language |
| SCI-IDEA | Uses facets and embedding-style criteria | BCS selection may overdepend on LLM scoring | Add non-LLM diversity/novelty proxies as target-hidden selection features |
| RQ-Bench | Shows LLM novelty judges can be misleading | BCS relies on LLM judge for Hit@10 and possibly selection | Add judge robustness, anti-mirage selection checks, and avoid claiming absolute novelty |
| SciAidanBench | Shows model capability is jagged and ensembles can help | BCS currently has only one main model in Phase 2 | Keep MiMo v2.5-pro main, but require MiMo v2.5 robustness before cross-model claims |

The main novelty cannot be "we generate more candidates." That is too close to FlowPIE/Nova and broader test-time search. The defensible novelty is:

> A lightweight, leakage-controlled, target-hidden fixed-output-budget study of structured and evolutionary candidate search on Sci-Reasoning Hit@10, including negative evidence for naive pattern conditioning and explicit judge-bias safeguards.

## Plan Improvements

### Keep

- Keep Direct-10 enriched rejudge as the main baseline.
- Keep plain BCS-50 as the simplest search-budget baseline.
- Keep PGCR as a negative ablation unless corrected results overturn it.
- Keep MiMo v2.5-pro as the Phase 2 main model and MiMo v2.5 as Phase 3 robustness.

### Add

Add a lightweight variant called **SE-BCS: Structured-Evolutionary Budgeted Candidate Search**.

SE-BCS remains target-hidden and fixed-output:

1. Extract compact predecessor structures: problem, method, evidence, limitation, and cross-paper relation triples.
2. Generate seed candidates from these structures.
3. Generate additional candidates through cheap crossover and mutation prompts.
4. Select exactly 10 with target-hidden quality, diversity, and anti-mirage features.
5. Judge only after selection using target title and enriched contribution.

SE-BCS should be an ablation or improved variant, not an unconditional replacement for BCS until it wins on the full 77-target set.

### Add Anti-Mirage Selection Features

Because RQ-Bench warns that LLM novelty judgment can be misleading, selection should include at least one non-LLM or weakly model-dependent diagnostic:

- intra-set diversity by TF-IDF or embedding cosine distance,
- candidate-vs-predecessor lexical overlap penalty,
- duplicate and near-duplicate detection,
- judge-prompt robustness on a sampled subset.

Do not claim these prove human-level novelty. Use them as safeguards against homogeneous or source-bound candidates.

### Add Related-Work Pressure Tests

The paper must explicitly distinguish from:

- Graph2Idea: no heavy KG, focus on Sci-Reasoning Hit@10 and fixed-output budget.
- FlowPIE/Nova: no large iterative literature search, only bounded lightweight evolution.
- LDC: no RL or fine-tuning, only inference-time search/selection.
- RQ-Bench/human study: judge limitations are a core threat model, not an afterthought.

### Updated ACML Story

Preferred story after this search:

> Existing scientific ideation systems increasingly use retrieval, graphs, or evolutionary search, but it is unclear how much of the gain comes from larger candidate budgets under leakage-controlled Sci-Reasoning evaluation. We isolate this question with fixed-output target-hidden candidate search, then test whether lightweight structure and evolution improve Hit@10 without heavy training or a full graph database.

This story is more defensible than claiming a broad new ideation agent.
