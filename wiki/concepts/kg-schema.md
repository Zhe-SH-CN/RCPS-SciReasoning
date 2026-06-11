---
type: concept
created: 2026-06-02
updated: 2026-06-02
tags: [knowledge-graph, schema, ontology, construction, paradigm]
---

# Knowledge Graph Schema（模式）

> Schema 是知识图谱的「骨架」——定义图谱允许存在的实体类型、关系类型和约束，但不包含具体数据。

## 三层结构

| 层次 | 术语 | 示例 |
|------|------|------|
| 实体类型 | Class / Entity Type | Person, Paper, Method, Dataset, Metric |
| 关系类型 | Property / Relation | cites, proposes, evaluates_on, authored_by |
| 约束 | Domain & Range | proposes: Person → Method |

## 两种范式

### Schema-based（先定义再抽取）
- 先由领域专家或 LLM 定义 ontology
- 再按 schema 约束做信息抽取
- 代表：OntoEKG, 传统 IE pipeline, Intern-Atlas
- **优点**：一致性好、可控、易维护
- **缺点**：需要领域专家、扩展性差、跨领域迁移难

### Schema-free（边抽取边归纳）
- 不预定义 schema，LLM 同时提取 triples + 归纳 schema
- 用 conceptualization 把实例组织成语义类别
- 代表：AutoSchemaKG（95% 人工对齐度，零人工干预）
- **优点**：灵活、适应新领域、无需人工、可扩展到 web-scale
- **缺点**：质量不稳定、可能产生冗余/冲突、调试难

### Hybrid（混合路线）
- 部分 schema 预定义 + 部分自动归纳
- 趋势方向：用 LLM 辅助 ontology refinement 而非完全自由生成

## 关键技术

- **Ontology Engineering**：手工或半自动定义 class hierarchy + property constraints
- **Schema Induction**：从已有 KG 或文本中自动推断 schema（AutoSchemaKG 的核心贡献）
- **Conceptualization**：将具体实例归纳为抽象语义类别（schema-free 路线的关键步骤）
- **Ontology Alignment**：对齐不同来源的 schema（跨 KG 融合的核心问题）

## 在 KG Construction 中的位置

```
原始文本 → [Schema?] → Entity Extraction → Relation Extraction → Schema Alignment → KG
                ↑                                                          ↑
          ontology 预定义                                            schema 后处理
          (schema-based)                                          (schema-free 自动归纳)
```

## 相关论文

- [AutoSchemaKG](../sources/bai-autoschemakg.md): schema-free 标杆，50M 文档 → 900M 节点 KG
- [OntoEKG](../sources/ontodekg.md): schema-based 企业级本体构建
- [Intern-Atlas](../sources/wu-intern-atlas.md): schema-based 方法演化图谱
- [SciAtlas](../sources/qiao-sciatlas.md): 混合路线，大规模学术 KG
- [LLM-empowered KGC Survey](../sources/llm-empowered-kgc-survey.md): 全面综述 schema-based vs schema-free

## Open Questions

- Schema-free 在高精度领域（医疗、法律）能否达到 schema-based 的质量？
- Dynamic schema（随数据演化自动调整）是否可行？
- Schema induction 的 evaluation 标准是什么？（AutoSchemaKG 用人工对齐度，但不够全面）
