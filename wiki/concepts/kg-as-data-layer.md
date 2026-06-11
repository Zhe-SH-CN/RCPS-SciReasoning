---
type: concept
created: 2026-05-30
updated: 2026-05-30
tags: [knowledge-graph, data-layer, llm-agent]
---

# Knowledge Graph as Data Layer for LLM Agents

> 在 LLM Agent 系统中，用 Knowledge Graph 替代 flat document store（JSON/YAML/CSV）作为数据层，解决 Agent 数据访问瓶颈。

## 核心发现

- 对于结构化运维领域，**数据模型是主要瓶颈**，不是 LLM 编排
- KG 数据层让三代 GPT 模型（GPT-4, GPT-4o, gpt-4.1）分数紧密聚集
- 确定性 graph handler 几乎完美（99-100%），说明数据正确后推理不是问题

## 构建方式（本文 ETL pipeline）

1. EAMLite → 设备层级（Site → Location → Equipment）
2. CouchDB → 传感器元数据（Sensor nodes）
3. FMSR YAML → 故障模式（FailureMode nodes + 384-dim embeddings）
4. Event CSV → 事件（Event nodes + 时间索引）
5. 手工添加 depends_on / shares_system_with 拓扑

## Key metrics

- 14 node labels, 21 edge types, 1360 nodes, ~2500 edges
- 384-dim Sentence-BERT embeddings + HNSW vector index
- OpenCypher 查询支持

## Sources

- [Kunkunuru et al. 2026](../sources/kunkunuru-kg-asset-ops.md)

## Related

- [[inverted-llm-usage]]
- [[assetopsbench]]
