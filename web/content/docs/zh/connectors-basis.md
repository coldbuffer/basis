---
title: Basis 连接器运行时（BOCP 宿主）
sidebarTitle: 连接器（Basis）
description: Basis BOCP 参考宿主的规范性期望——本体投影与 Agent MCP——及已知接线缺口。
---

# Basis 连接器运行时

本文说明 **Basis** 作为 **宿主** 如何实现 [BOCP v2.0](bocp.zh.md)。[双消费者](#双消费者一份-manifest) 一节为 **Basis 产品层面的要求**；其余章节除非标明均为资料性。

其他 BOCP 运行时不必沿用这些 HTTP 路径或 MCP 工具名。

---

## 双消费者（一份 manifest）

Provider bundle（`connector.yaml`）**只写一份**。BOCP 运行时把 `actions[].rest.operations` / `sql.operations` 编译为 **CHECK**、**DISCOVER**、**LIST**、**MUTATE**、**INVOKE**（见 [bocp.zh.md §10](bocp.zh.md#10-运行时原语)）。

完整的 **Basis 宿主必须** 在同一运行时上提供 **两条一等公民绑定**：

| 消费者 | 绑定 | 如何触达原语 |
|--------|------|----------------|
| **本体 / 账本** | `source_table_mappings`、入向 sync、`entity_sync_outbox` 写回 | `connector_sync` 与审批后的 outbox 内调用 `ConnectorRuntime.read_stream` / `mutate_stream` |
| **智能体（MCP）** | 工作区 MCP 工具（及对应的 OpenAPI） | **直接**调用 §10 原语：`service` + `action_id` + 原语种类 + `action_params` / `scope` — LIST **不要求**先建 mapping |

示例：GitHub `issues` 的 `rest.operations.list` 既用于定时同步进证据账本，也用于智能体经 MCP 拉取当前 issue 列表。Manifest 不分叉，只有宿主入口不同。

智能体 **不得** 依赖第二份 manifest、按厂商路径生成的 OpenAPI，或「每个 YAML operation 键一个 MCP tool」。宿主 **应当** 暴露少量稳定的原语级 MCP（或等价 API），而不是仅提供账本导向工具。

**Basis 参考宿主 — 实现状态**

| 绑定 | 状态 |
|------|------|
| 账本 / 投影 | **已交付** — HTTP `/api/v1/workspaces/{workspace_id}/connectors/*`，MCP `sync_connector_table_mapping`、`propose_entity_writeback` 等 |
| 智能体原语 | **已交付** — MCP `invoke_connector_primitive` 与 `tools/list` 按 action 展开的 `connector_{service}__{action_id}__{suffix}`；HTTP `POST …/invoke-primitive` |
| 控制台 UI | **已交付** — `/workspaces/{workspace_id}/connectors`（`web/src/modules/connectors/`）；平台 allowlist：`/admin/connectors` |

策略：`action_policy.entities`（如 `github:issues.list`）及 `default_entity_read_mode` / `default_entity_write_mode`。

---

## 执行器（资料性）

规范性 Manifest：`rest.operations` / `sql.operations`（[bocp.zh.md §7](bocp.zh.md#7-actions)）。Basis 编译为内部适配器：

| 执行器 | Basis 适配器 | 说明 |
|--------|--------------|------|
| `rest.operations` | `rest_declarative` | `list` → LIST；`create`/`update`/… → MUTATE |
| `sql.operations` | `sql_alchemy` | `discover` + `sql_inspector`；表 scope 由宿主 `external_table` / `action_params` 提供 |

所有 Manifest 均按 BOCP v2.0 校验，不接受其他线上版本。

Basis 特有的 REST 扩展（其他 BOCP 宿主忽略）：entity action 上的 `x-basis-dynamic-schema-loader`、`x-basis-record-fields-unwrap-path`、`x-basis-record-filter-jinja`、`x-basis-partition-router`，用于保留 v2 线上格式未标准化的适配器能力。

---

## 代码地图

| 组件 | 位置 |
|------|------|
| Runtime | `basis/domain/integration/runtime.py` |
| REST adapter | `basis/domain/integration/adapters/rest/` |
| SQL adapter | `basis/domain/integration/adapters/sql/` |
| Provider bundles | `basis/domain/integration/providers/` |
| Manifest 模式 | `basis/domain/integration/manifest_schema.py` |
| 目录 | `basis/domain/integration/catalog.py` |
| 构建随版 bundle | `scripts/connectors/build_connector_manifests.py` |

---

## 宿主 API

| 面 | 位置 |
|----|------|
| HTTP | `/api/v1/workspaces/{workspace_id}/connectors/*`（见 [openapi-v1.md](openapi-v1.md) 与 live `/openapi/v1.json`） |
| MCP | `basis/application/operations_connectors.py`（含 `invoke_connector_primitive`） |

持久化与工作区投影：[data-model.md](../data-model.md) §18。

---

## 校验

```bash
uv run pytest tests/test_bocp_phase1.py -q
```

SQL 集成测试（可选环境）：`tests/test_sql_connector_integration.py`。

---

## 已知缺口（资料性）

- 路由变更后请运行 `uv run python scripts/openapi/generate-openapi-v1.py` 更新 OpenAPI 快照。

---

## 相关文档

- bocp.md(bocp.md) / bocp.zh.md(bocp.zh.md) — 协议规范
- [product.md](product.md) — 连接器产品架构
