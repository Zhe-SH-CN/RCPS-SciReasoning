# KG Construction Research Wiki

> Karpathy-style LLM-managed wiki for Knowledge Graph Construction research.
> Built by Knot 🪢 for Zhe's third paper.

## Quick Start

1. **Read this file first** — gives you the landscape
2. **Read `wiki/sources/`** — each file is a paper summary with key claims, methodology, and cross-references
3. **Read `wiki/concepts/`** — cross-cutting concepts that span multiple papers
4. **Read `wiki/index.md`** — master index with all pages

## Directory Structure

```
kg-research/
├── README.md                    ← You are here
├── AGENTS.md                    ← Wiki maintenance rules
│
├── raw/                         ← PDF 原文（20 篇）
│   ├── 2605.22878.pdf           ← SciAtlas
│   ├── 2505.23628.pdf           ← AutoSchemaKG
│   ├── 2604.28158.pdf           ← Intern-Atlas
│   ├── 2510.23341.pdf           ← LightKGG
│   ├── 2507.03226.pdf           ← Efficient KG for RAG
│   ├── 2604.19137.pdf           ← LLHKG
│   ├── 2602.01276.pdf           ← OntoEKG
│   ├── 2603.20059.pdf           ← DIAL-KG
│   ├── 2510.20345.pdf           ← LLM-empowered KGC Survey
│   ├── 2603.25862.pdf           ← Methods for KGC from Text
│   ├── 2504.02670.pdf           ← KGoT
│   ├── 2410.16597.pdf           ← SynthKG
│   ├── 2605.05476.pdf           ← Unified Benchmark
│   ├── 2601.04577.pdf           ← Sci-Reasoning
│   ├── nature-materials-*.pdf   ← Nature Materials (concept graphs)
│   └── ... (5 more)
│
├── wiki/
│   ├── index.md                 ← Master index (all pages listed)
│   ├── log.md                   ← Ingest changelog
│   ├── hot.md                   ← Hot topics & open questions
│   │
│   ├── sources/                 ← Paper summaries (16 篇)
│   │   ├── qiao-sciatlas.md
│   │   ├── bai-autoschemakg.md
│   │   ├── wu-intern-atlas.md
│   │   ├── lightkgg.md
│   │   ├── efficient-kgc-rag.md
│   │   ├── llhkg.md
│   │   ├── ontodekg.md
│   │   ├── dial-kg.md
│   │   ├── llm-empowered-kgc-survey.md
│   │   ├── methods-kgc-text.md
│   │   ├── kgot.md
│   │   ├── luo-synthkg.md
│   │   ├── unified-kgc-benchmark.md
│   │   ├── liu-sci-reasoning.md
│   │   ├── kunkunuru-kg-asset-ops.md
│   │   └── nature-materials-concept-graphs.md
│   │
│   ├── concepts/                ← Cross-cutting concepts (14 个)
│   │   ├── kg-schema.md         ← Schema-based vs Schema-free
│   │   ├── schema-based-kgc.md
│   │   ├── schema-free-kgc.md
│   │   ├── incremental-kgc.md
│   │   ├── ontology-construction.md
│   │   ├── hyper-relational-kg.md
│   │   ├── knowledge-fusion.md
│   │   ├── hybrid-retrieval.md
│   │   ├── kg-based-reasoning.md
│   │   ├── kg-as-data-layer.md
│   │   ├── inverted-llm-usage.md
│   │   ├── topology-enhanced-relation-inference.md
│   │   ├── meta-knowledge-base.md
│   │   └── soft-deprecation.md
│   │
│   ├── entities/                ← Researcher profiles (10 人)
│   │   └── *.md
│   │
│   ├── notes/                   ← Working notes (empty)
│   └── reports/                 ← Reports (empty)
│
└── .git/                        ← Git history
```

## Paper Coverage

| # | Paper | ArXiv ID | Core Contribution |
|---|-------|----------|-------------------|
| 1 | SciAtlas | 2605.22878 | 43M papers, 157M entities, 3B triples — panoramic academic KG |
| 2 | AutoSchemaKG | 2505.23628 | Autonomous schema induction, 900M+ nodes, 5.9B edges |
| 3 | Intern-Atlas | 2604.28158 | Methodological evolution graph for AI research |
| 4 | SynthKG | 2410.16597 | Synthetic data + distillation for KG scaling (ICLR 2026) |
| 5 | LightKGG | 2510.23341 | SLM achieves 96-97% of LLM KG quality |
| 6 | Efficient KG for RAG | 2507.03226 | LLM-free KG construction + hybrid retrieval |
| 7 | LLHKG | 2604.19137 | Lightweight LLM for hyper-relational KG |
| 8 | OntoEKG | 2602.01276 | LLM-driven enterprise ontology construction |
| 9 | DIAL-KG | 2603.20059 | Closed-loop incremental KGC + dynamic schema |
| 10 | LLM-empowered KGC Survey | 2510.20345 | Comprehensive survey: schema-based vs schema-free |
| 11 | Methods for KGC | 2603.25862 | Practical LLM-powered KGC across 3 domains |
| 12 | KGoT | 2504.02670 | KG of Thoughts — KG as reasoning intermediate |
| 13 | Unified Benchmark | 2605.05476 | Dual-purpose benchmark: GNN robustness + KGC quality |
| 14 | Sci-Reasoning | 2601.04577 | 15 thinking patterns from NeurIPS/ICML/ICLR papers |
| 15 | Nature Materials | s42256-026-01206-y | Concept graphs for predicting research directions |
| 16 | KG as Data Layer | 2605.26874 | KG as data layer for LLM-based industrial agents |

## Key Research Directions (from the wiki)

1. **大规模学术图谱** — SciAtlas, Intern-Atlas → 为 AI Agent 构建科研基础设施
2. **全自动 Schema** — AutoSchemaKG → 去掉人工 schema，LLM 自己归纳
3. **高效/低成本** — SynthKG, LightKGG, Efficient KG → 降低构建成本
4. **质量验证** — Unified Benchmark, FactCheck → 构建完怎么评估图质量
5. **Schema-based vs Schema-free** — OntoEKG vs AutoSchemaKG → 两条路线之争
6. **增量/动态** — DIAL-KG → 闭环治理 + 动态 schema 演化

## How to Use This Wiki

### For Claude Opus / LLM reading:
1. Start with `wiki/sources/*.md` — each has structured summary with key claims and cross-refs
2. Cross-reference with `wiki/concepts/*.md` for terminology and relationships
3. Check `wiki/hot.md` for open questions and research gaps
4. Use `wiki/index.md` for navigation

### For Zhe's group meeting prep:
- Focus on `wiki/sources/wu-intern-atlas.md` (your baseline)
- Compare with `wiki/sources/qiao-sciatlas.md` (competitor)
- Read `wiki/concepts/kg-schema.md` for the schema concept explanation
- Check `wiki/hot.md` for potential research gaps

---

*Last updated: 2026-06-02 | 16 papers ingested | 14 concepts | 10 entities*
*Built with arxiv-ingest + llm-wiki-manager skills*
