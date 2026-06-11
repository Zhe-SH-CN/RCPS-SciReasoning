---
type: concept
created: 2026-05-30
updated: 2026-05-30
tags: [llm-agent, knowledge-graph, paradigm]
---

# Inverted LLM Usage

> 一种 KG + LLM Agent 范式：LLM 不直接推理原始数据，而是从 typed schema 生成结构化查询（如 Cypher），图数据库确定性执行查询并返回结果。

## 核心思想

传统模式：LLM → 工具调用 → flat data → LLM 解读结果（全靠 LLM）
Inverted 模式：LLM → 生成 Cypher → KG 确定性执行 → 结果直接可用

## 优势

- LLM 只负责"翻译"（自然语言 → 结构化查询），不负责"计算"
- 图数据库处理 counting、joining、traversing 等 LLM 容易出错的操作
- 同一 GPT-4 模型：flat docs 65% → KG 上 82-83%

## 局限

- 需要预先构建 typed schema（schema 质量直接影响性能）
- 不适用于需要 ML 推理的场景（如时序预测 TSFM）
- 图的构建仍是人工/半自动过程

## Sources

- [Kunkunuru et al. 2026](../sources/kunkunuru-kg-asset-ops.md): 首次在 AssetOpsBench 上系统验证此范式

## Related

- [[kg-as-data-layer]]
- [[llm-cypher-generation]]
