---
title: BOCP v2.0 — 连接器 Manifest 协议
sidebarTitle: BOCP 规范
description: BOCP v2.0 规范性说明 + 零基础读者指南（Manifest、原语、operations、宿主），与英文版同步。
---

# Basis Open Connector Protocol (BOCP) 版本 2.0

| | |
|---|---|
| **文档** | BOCP v2.0 |
| **状态** | Basis Standards Track（Basis 发行版规范性文档） |
| **格式** | YAML Manifest + 本规范 |
| **模式伴生** | `basis/domain/integration/manifest_schema.py`（Pydantic v2） |
| **相关** | [runtime.zh.md](runtime.zh.md)（Basis 宿主；非规范性） |

---

## 摘要

本文定义 **Basis Open Connector Protocol (BOCP)**：**消费者无关**、**传输可插拔** 的外部 **Provider** Manifest——如何 **认证**，以及符合规范的 **运行时** 可执行哪些 **动作（actions）**。

Manifest 声明 **`auth`** 与 **`actions`**。每条动作为 **entity**（DISCOVER、LIST、可选 MUTATE）或 **procedure**（INVOKE）。到达上游仅通过 **`rest` / `sql` 执行器** 内的 **`operations` 映射**（HTTP method、path、body 等）由宿主编译执行。v2 仅定义 `rest` 与 `sql` 的执行语义；`graphql` / `grpc` 只是附件提示，不是可执行执行器。

运行时原语：**CHECK**、**DISCOVER**、**LIST**、**MUTATE**、**INVOKE**。连接、策略、调度与工作区投影为 **宿主绑定**，**禁止** 写入 `connector.yaml`。

线上 `version` **必须** 为 `"2.0"`；其他版本不接受。

**首次阅读：** 请先读 [BOCP 导读](/docs/bocp-guide)，再读本规范中的 [§1.6 读者指南](#16-读者指南从这里开始) 与 [附录 D](#附录-d-教程从零到一次-list-调用)。

---

## 本文档状态

体例参照 IETF RFC（简化 [RFC 7841](https://www.rfc-editor.org/info/rfc7841)）。BOCP **不是** IETF 标准 track，除非另行发布。

声称符合 BOCP v2.0 的实现 **必须** 满足第 11 节（符合性）。

> 节号与英文版 bocp.md(./bocp.md) 一致；YAML 字段名、枚举与代码标识保持英文。

---

## 目录

1. [引言](#1-引言)（含 [§1.6 读者指南](#16-读者指南从这里开始)）  
2. [术语](#2-术语)  
3. [记法](#3-记法)  
4. [协议概览](#4-协议概览)  
5. [Provider Bundle](#5-provider-bundle)  
6. [Connector Manifest](#6-connector-manifest)  
7. [动作（Actions）](#7-动作actions)  
8. [认证](#8-认证)  
9. [插值](#9-插值)  
10. [运行时原语](#10-运行时原语)  
11. [符合性](#11-符合性)  
12. [安全考虑](#12-安全考虑)  
13. [IANA 考虑](#13-iana-考虑)  
14. [参考文献](#14-参考文献)  
15. [修订历史](#15-修订历史)  
附录 A. [Operation 标识符](#附录-a-operation-标识符)  
附录 B. [模式索引](#附录-b-模式索引)  
附录 C. [GitHub 示例](#附录-c-github-示例)  
附录 D. [教程：从零到一次 LIST 调用](#附录-d-教程从零到一次-list-调用)  

---

## 1. 引言

### 1.1 规范性用语

关键词 "**MUST**"、"**MUST NOT**"、"**REQUIRED**"、"**SHALL**"、"**SHALL NOT**"、"**SHOULD**"、"**SHOULD NOT**"、"**RECOMMENDED**"、"**NOT RECOMMENDED**"、"**MAY**"、"**OPTIONAL**" 仅在全大写时按 BCP 14 [[RFC2119](https://www.rfc-editor.org/info/rfc2119)] [[RFC8174](https://www.rfc-editor.org/info/rfc8174)] 解释。

### 1.2 问题陈述

集成需要可移植地描述 **如何认证** 与 **存在哪些操作**，而不预设调用方是 UI、智能体还是批处理，也不把 Manifest 钉死在某一种线上协议。厂商 API 描述（如 OpenAPI）通常缺少连接表单、多种认证模式，以及统一的「列举 / 变更记录」模型。BOCP 提供一份小 Manifest 与固定的原语集合；**具体 HTTP/SQL 如何执行** 由宿主的执行器层解释 `rest.operations` / `sql.operations`。

### 1.3 目标

1. **消费者无关** — 禁止账本、本体、MCP 专用字段。  
2. **传输可插拔** — Manifest 不锁定单一上游协议；v2 的实体执行器为 `rest` / `sql`，`graphql` / `grpc` 仅为附件提示，不定义执行语义。  
3. **简单** — 单一 `actions[]`，`kind` 为 `entity` 或 `procedure`。  
4. **可扩展** — `operations` 与宿主适配器可在兼容前提下演进。  
5. **保留上游** — GitHub、Postgres 等厂商 **不必** 实现 BOCP；只有 **宿主** 读 Manifest 并调用其真实 API。

### 1.4 非目标

不规定：密钥存储、OAuth 客户端注册、token 刷新、允许列表、审计、图谱映射、原语如何暴露为 HTTP/MCP/CLI（第 4.3 节宿主绑定）。

### 1.5 与其他规范的关系

| 规范 | 关系 |
|------|------|
| **OpenAPI 3.x** | **可以** 挂在 `spec` 下作文档；规范性执行以 `rest.operations` / `sql.operations` 为准，而非厂商 path 列表。附件是 **可选** 的：除非 `spec.openapi` 明确命名，宿主 **不得** 假定 `openapi.yaml` 存在。 |
| **OAuth 2.0** [[RFC6749](https://www.rfc-editor.org/info/rfc6749)] | `oauth2` 模式嵌入授权/换票 URL；token 存储由宿主负责。 |
| **JSON Schema** | **可以** 描述 procedure 的 `input_schema`；INVOKE 入参校验由宿主定义。 |

### 1.6 读者指南（从这里开始）

面向 **从未接触过 BOCP** 的读者。后文规范性条款仍使用 BCP 14 关键词；此处用通俗语言说明概念。

#### 1.6.1 BOCP 解决什么问题

外部系统（SaaS、数据库）各有不同的 API 与认证。集成代码反复实现「连上 → 拉列表 → 改一条 → 调 RPC」。BOCP 为每个外部产品（**Provider**）提供一份 **YAML Manifest**，回答：

1. **用户怎么连？**（OAuth、API Key、DSN 等 — §8）  
2. **有哪些业务对象？**（`actions[]` 目录 — §7）  
3. **每种操作如何打到上游？**（`rest.operations` 或 `sql.operations` — §7.5–7.6）

Manifest **不含密码**；用户在 **宿主** 里保存 **Connection**（密钥 + 配置）。

#### 1.6.2 三层（不要混用）

| 层 | 含义 | 例子 |
|----|------|------|
| **Manifest** | 随 Provider 发布的 `connector.yaml` | 声明 `issues` 的 LIST 路径模板 |
| **Connection** | 某租户保存的连接 | PAT、`connection_config.owner/repo` |
| **原语调用** | 一次运行时操作 | 对 `action_id: issues` 执行 LIST |

#### 1.6.3 与厂商 OpenAPI 的区别

| | 厂商 OpenAPI | BOCP Manifest |
|---|--------------|---------------|
| 重点 | HTTP 路径与 JSON Schema | 认证 + 稳定的 **业务动作** |
| 调用方式 | 按端点生成客户端 | 五种 **原语**（§10） |
| 智能体 / 同步 | 未定义 | **同一份** Manifest 两用 |

#### 1.6.4 五种原语

| 原语 | 适用 | 含义 |
|------|------|------|
| CHECK | 连接 | 凭据是否有效 |
| DISCOVER | entity | 字段/schema |
| LIST | entity | 拉一批记录 |
| MUTATE | entity | create / update / upsert / delete |
| INVOKE | procedure | 任意 RPC |

#### 1.6.5 `actions[]` 与 `operations`

- 每条 action 有 `kind: entity | procedure` 与唯一 `id`（调用时的 `action_id`）。  
- 线上配置只在 **`rest`** 或 **`sql`** 下的 **`operations`** 映射里；v2 **没有** 顶层 `list`/`writes`。  
- 键名 `list`、`create` 等表示 **操作类型**，由运行时映射到 LIST / MUTATE，不是第二层 Manifest。

#### 1.6.6 作用域：`action_params` 与模板

路径中的 `{{config.owner}}`、`{{external_id}}`、`{{patch}}` 由连接配置、每次调用的 **`action_params`** 与变更集填充（§9）。**`connection_config` 定义的键不可被 `action_params` 覆盖**；`action_params` 只填补缺失的键。

#### 1.6.7 双消费者

同一份 Manifest 既可用于 **账本/本体同步**，也可供 **智能体** 直接 LIST（§4.3.1、§10.4）。MCP 工具名属于宿主，不在 YAML 里。

#### 1.6.8 阅读路线

| 目标 | 章节 |
|------|------|
| 编写 Provider | §5–8、附录 C–D |
| 应用侧调用 | §10、附录 D |
| 实现宿主 | §4、§10–11、[runtime.zh.md](runtime.zh.md) |

---

## 2. 术语

| 术语 | 定义 |
|------|------|
| **Provider** | 由 `service` 标识的外部产品。 |
| **Bundle** | `providers/{service}.yaml` 及可选同目录附件（如 `{service}.openapi.yaml`）。 |
| **Manifest** | 符合 v2 `ConnectorManifest` 的 `{service}.yaml`。 |
| **Connection** | `auth_type`、`connection_config`、`credentials`（不在 Manifest 内）。 |
| **Action** | 目录项：entity 或 procedure。 |
| **Entity** | `kind: entity`；DISCOVER / LIST / 可选 MUTATE。 |
| **Procedure** | `kind: procedure`；INVOKE。 |
| **Executor** | action 上的 `rest` 或 `sql` 块，内含 `operations`。 |
| **Operation 键** | `operations` 内的名字（如 `list`），映射到原语（§7.4）。 |
| **`action_id`** | action 的 `id` 字段，每次原语调用必带。 |
| **`action_params`** | 单次调用的作用域对象；只填补缺失的 `{{config.*}}` 键，不覆盖 `connection_config`（§9）。 |
| **Primitive** | CHECK、DISCOVER、LIST、MUTATE、INVOKE。 |
| **Host** | 加载 Manifest、存连接、暴露 HTTP/MCP、策略。 |
| **Runtime** | 执行原语的库（无 UI）。 |
| **宿主绑定** | 账本 mapping、MCP 工具名等 **不** 写入 Manifest 的宿主功能。 |
| **扩展字段** | 任何以 `x-` 开头的对象成员；符合规范的运行时忽略它，加载器保留它。 |

---

## 3. 记法

- Manifest 序列化 **必须** 为 YAML 1.2，除非宿主文档另有说明；Basis 使用 UTF-8 YAML。  
- 正文中字段名使用 `monospace`，与 Manifest 键名一致。  
- `service` 模式：`^[a-z0-9][a-z0-9_-]*$`。  
- 本文档对应的 Manifest `version` **必须** 为 `"2.0"`。  
- 类型默认遵循 JSON 数据模型，另有说明时除外。  
- 任何以 `x-` 开头的对象成员都是 **扩展字段**；其他未声明成员一律非法。  
- 实体 `rest.operations` 的键封闭为 `list`、`create`、`update`、`upsert`、`delete`；`sql.operations` 另允许 `discover`；procedure 的 `rest.operations` **必须** 且只能包含 `invoke`。以 `x-` 开头的键是忽略的扩展，不是 operation。  

权威机器可读模式：`basis/domain/integration/manifest_schema.py`。本规范与模式文件 **应当** 同步维护。

---

## 4. 协议概览

### 4.1 分层

```
  +------------------+
  |  宿主绑定        |  连接、策略、投影、HTTP/MCP/CLI
  +--------+---------+
           |
  +--------v---------+
  |  BOCP 运行时     |  CHECK, DISCOVER, LIST, MUTATE, INVOKE
  +--------+---------+
           |
  +--------v---------+
  |  BOCP Manifest   |  auth, actions, spec
  +--------+---------+
           |
  +--------v---------+
  |  上游系统        |  （由实现层决定）
  +------------------+
```

### 4.2 原语与动作

| `kind` | 原语 |
|--------|------|
| `entity` | DISCOVER、LIST、MUTATE（`operations` 中的 `create`/`update`/…） |
| `procedure` | INVOKE |

CHECK 针对 **连接**（认证），不针对单个 action id。

任何消费者 **可以** 调用运行时暴露的任意原语；BOCP **不** 把原语绑定到「智能体」或「同步」角色。

同一份 Manifest 与运行时 **必须** 同时服务于 **知识投影**（账本同步、受控写回）与 **交互式智能体**（例如不经 mapping 的 MCP LIST）。Manifest 不选消费者；**宿主** 通过一条或多条绑定接线（§4.3.1）。

### 4.3 宿主绑定

[data-model.md](../data-model.md) §18 等 **禁止** 出现在 `connector.yaml` 内。

BOCP **不** 规定 HTTP 路径名或 MCP 工具 id。宿主 **应当** 在面向智能体的面上用稳定选择器暴露 §10 原语：`service`、`action_id`、原语种类（`discover`、`list`、`mutate`、`invoke`），以及宿主提供的 `action_params` / `scope`（§10）。

### 4.3.1 双消费者（资料性）

典型产品宿主（如 [runtime.zh.md](runtime.zh.md)）对 **同一** BOCP 运行时挂 **两条并行绑定**：

| 消费者 | 典型宿主绑定 | 原语用途 |
|--------|--------------|----------|
| **本体 / 账本** | 流→实体 mapping、定时入向 sync、outbox 写回 | 同步与审批出向时的 LIST / MUTATE |
| **智能体（MCP、对话工具）** | 工作区 MCP / OpenAPI 上的原语 API | DISCOVER、LIST、MUTATE、INVOKE — **无需** mapping 行 |

任一绑定 **不得** 要求第二份 Manifest 或重复 operation 定义。智能体侧 LIST **必须** 在无账本配置时仍有效（§10.4）。

---

## 5. Provider Bundle

### 5.1 布局

```
providers/
  {service}.yaml
  {service}.openapi.yaml   # 可选 REST 附件
```

`spec` 引用的可选附件见第 6 节。除「当 `spec` 要求时文件必须存在」外，BOCP v2 不定义附件语义；宿主在加载时校验目录布局。

### 5.2 加载规则

1. 文件名 **必须** 为 `{service}.yaml`，且与文件内 `service` 字段一致。  
2. 宿主 **必须** 拒绝无法通过模式校验的 Manifest。  
3. 宿主 **可以** 在启动时只读加载全部 Bundle。

### 5.3 `ProviderSpecReference`（`spec`）

| 字段 | 说明 |
|------|------|
| `protocol` | `rest`（默认）\| `sql` \| `graphql` \| `grpc` — **仅提示附件类型**，不是执行语义；v2 只有 `rest` / `sql` 执行器。 |
| `openapi`、`graphql`、`grpc` | 可选相对路径。声明了路径就 **必须** 存在；省略字段 **不** 隐含默认文件。 |

规范性执行 **必须** 使用 `actions[].rest` / `actions[].sql` 下的 `operations`，**不得** 默认按厂商 OpenAPI 的 path 项执行，除非宿主文档明确消费附件。宿主 **不得** 仅因 `protocol: rest` 就要求 `openapi.yaml` 存在。

---

## 6. Connector Manifest

| 字段 | 必填 | 说明 |
|------|------|------|
| `version` | 是 | **必须** 为 `"2.0"`。 |
| `service` | 是 | Provider 标识（第 3 节模式）。 |
| `display_name` | 是 | 目录展示名称。 |
| `description` | 否 | 长描述。 |
| `categories` | 否 | 字符串标签列表。 |
| `homepage_url`、`docs_url`、`icon_url` | 否 | URI。 |
| `spec` | 否 | 附件提示（第 5.3 节）。 |
| `auth` | 是 | 非空 `AuthSpec` 数组（第 8 节）。 |
| `actions` | 否 | 默认 `[]`。 |

Manifest 的任何对象 **禁止** 出现未声明字段，但以 `x-` 开头的 **扩展字段** 除外。Basis 通过共享基类强制执行。

---

## 7. 动作（Actions）

### 7.1 判别字段

`actions[]` 元素 **必须** 含 `kind`：`entity` | `procedure`。同一 Provider 内 `id` **必须** 唯一。

### 7.2 Entity（`kind: entity`）

实体元数据 **协议无关**；线上操作只放在 **`rest`** 或 **`sql`** 执行器块之一。

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 原语选择器 |
| `display_name` | 是 | 展示标签 |
| `description` | 否 | 说明；**建议** 写明需要的 `action_params`。 |
| `primary_key` | 否 | 字段名列表；默认 `["id"]`。 |
| `cursor_field` | 否 | 增量 LIST **推荐** 的水位字段名。 |
| `default_label_field` | 否 | UI/展示用默认标题字段。 |
| `fields` | 否 | 静态 DISCOVER 字段列表（`StreamFieldSpec`）。 |
| `rest` | 二选一 | HTTP 执行器 — `operations`（§7.5）。 |
| `sql` | 二选一 | SQL 执行器 — `operations`（§7.6）。 |

每条 entity **必须** 在执行器的 `operations` 中声明 `list`。`operations` 键是 **封闭集合**：

- REST：`list`、`create`、`update`、`upsert`、`delete`。  
- SQL：上述键再加 `discover`。  

加载器 **必须** 拒绝未知的、非 `x-` 前缀的 operation 键；静默忽略会让 Manifest 看起来支持它并不支持的操作。v2 不支持“只写” entity——此类调用应建模为 procedure。

若 `fields` 为空，且执行器未声明动态发现操作，DISCOVER 返回空 `fields` 数组。REST 的动态发现属于宿主扩展（例如放在 `x-` 字段下）；SQL 使用 `operations.discover`。

#### 7.2.1 `StreamFieldSpec`（实体字段）

| 字段 | 说明 |
|------|------|
| `name` | **必填** 字段名 |
| `data_type` | `string`、`integer`、`number`、`boolean`、`date`、`datetime`、`json`、`array` |
| `nullable` | 是否可空（布尔） |
| `primary_key` | 是否主键（布尔） |
| `fk_target_stream` | 可选；同 Provider 内另一 entity 的 `id` 提示 |
| `description` | 可选说明 |

#### 7.2.2 `action_id` 命名（资料性）

Provider 内 `id` **建议** 使用简短 `snake_case` 业务集合名（常为复数），例如 `issues`、`table_records`。**不要** 在 `id` 中加 `service` 前缀（已有顶层 `service`）。仓库名、表名等 scope **应当** 放在 `action_params` 或 `connection_config`，而非塞进 `id`。宿主侧策略/遥测逻辑 id 仍为 `{service}.{action_id}.{operation}`（附录 A）。

### 7.3 Procedure（`kind: procedure`）

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | INVOKE 时使用的稳定 id |
| `name` | 是 | 短名（可与 `id` 不同） |
| `display_name` | 是 | 展示标签 |
| `description` | 否 | **建议** 填写；宿主暴露 MCP 时尤其有用 |
| `input_schema`、`output_schema` | 否 | JSON Schema 片段 |
| `annotations` | 否 | `read_only_hint`、`destructive_hint`、`idempotent_hint` |
| `required_scopes` | 否 | OAuth scope 提示 |
| `rest` | 是 | `rest.operations` **必须且只能** 包含 `invoke` 键。 |

v2 不定义 `rest` 之外的 procedure 执行器；SQL 或 GraphQL procedure 不符合规范。

### 7.4 编写约定

1. **单一 `operations` 映射** — 同一实体的 HTTP/SQL 操作都在 `rest.operations` 或 `sql.operations` 下，不再使用顶层 `list`/`writes`。  
2. **封闭键集合** — 键 `list`→LIST；`create`/`update`/`upsert`/`delete`→MUTATE；procedure 的 `invoke`→INVOKE。不允许其他键。  
3. **不应当** 让同一上游效果同时出现在 entity 与 procedure；宿主 **可以** 在加载时告警，但不总能自动判定语义重复。

### 7.5 REST 执行器（`rest`）

```yaml
rest:
  operations:
    list:
      method: GET
      path: /repos/{{config.owner}}/{{config.repo}}/issues
      query: { state: all }
      pagination: { type: page, limit_param: per_page, page_request_param: page }
      incremental: { param: since }
    create:
      method: POST
      path: /repos/{{config.owner}}/{{config.repo}}/issues
      body: { patch: '{{patch}}' }
    update:
      method: PATCH
      path: /repos/{{config.owner}}/{{config.repo}}/issues/{{external_id}}
      body: { patch: '{{patch}}' }
```

#### 7.5.1 `RestOperationSpec`

| 字段 | 说明 |
|------|------|
| `method` | **必填** `GET`、`POST`、`PUT`、`PATCH`、`DELETE` |
| `path` | **必填** 路径或模板（§9 插值）；替换值按 URL 规则编码 |
| `query` | 可选；固定或模板化查询参数 |
| `headers` | 可选；额外请求头 |
| `body` | 可选；MUTATE 用 JSON 模板。`{"patch": "{{patch}}"}` 作为 **整个** body 时表示“用变更集替换顶层 body”；嵌套位置的 `{{patch}}` 解析为变更集对象。 |
| `pagination` | 可选 `PaginatorSpec`，通常挂在 `list` |
| `incremental` | 可选 `{ param: <name>, inject_into: query \| body \| header }`；LIST 增量水位，默认 `query` |
| `records` | 可选；响应 JSON 中记录数组的路径段。省略或为空表示 **整个响应体** 即记录集合。 |

operation 键按 entity / procedure 校验，见 §7.2–7.4。

#### 7.5.2 `PaginatorSpec`（资料性）

| 字段 | 说明 |
|------|------|
| `type` | `none`、`cursor`、`offset`、`page`、`link` |
| `page_size` | 默认每页大小提示 |
| `limit_param` | 限制条数的 query/body 参数名 |
| `inject_into` | `query`、`body`、`header` |
| `cursor_request_param` / `cursor_response_path` | 游标分页 |
| `offset_request_param` | 偏移分页 |
| `page_request_param` | 页码分页（如 GitHub `page`） |
| `link_header_rel` / `link_response_path` | Link 头或 JSON 内 next 链接 |
| `stop_condition_jinja` | 可选停止条件表达式 |

`page_size` 只是每页请求提示，不是 LIST 返回上限。宿主 **可以** 内部连续翻页，直到达到原语的 `limit` 或上游耗尽；**必须** 在 `limit` 处停止。LIST 输出契约见 §10.4。

宿主将 `rest.operations` 编译为 HTTP 客户端 / REST 适配器层（[runtime.zh.md](runtime.zh.md)）。

### 7.6 SQL 执行器（`entity.sql`）

```yaml
sql:
  operations:
    discover: { type: sql_inspector }
    list: {}
    create: {}
    update: {}
```

允许的 operation 键为 `list`、`discover`、`create`、`update`、`upsert`、`delete`，其中 `list` **必填**。`discover` 等 operation 值由 SQL/ORM 执行层解释（如 SQLAlchemy 反射）；`list` / `create` / `update` 等键映射 LIST / MUTATE。表名 scope 在运行时由宿主传入（如 `external_table`），执行器 **必须** 按标识符校验/引用。

---

## 8. 认证

每条 `AuthSpec` 描述一种 **认证模式**。运行时 Connection 的 `auth_type` **必须** 与其中 **恰好一条** 匹配。

### 8.1 `auth_mode` 取值

`none`、`api_key`、`basic`、`two_step`、`oauth2`、`oauth2_cc`、`oauth1`、`jwt`、`aws_sigv4`、`app`、`database_dsn`、`custom`。

### 8.2 通用字段

| 字段 | 要求 |
|------|------|
| `base_url` | REST 连接 **必填**；**不得** 重复本应写在 action `operations` 里的路径。 |
| `headers`、`query_params` | **可以** 含插值后的密钥（§9）。 |
| `connection_config`、`credentials` | `ConfigFieldSpec` 表单定义。 |
| `oauth2` | 当 `auth_mode` 为 `oauth2` 或 `oauth2_cc` 时 **必填**。 |
| `two_step` | 当 `auth_mode` 为 `two_step` 时 **必填**。 |
| `check` | **可选**；存在时 CHECK 原语使用。 |
| `quotas` | **可选** 限流元数据。 |

#### 8.2.1 请求认证注入（规范性）

`auth_mode` 决定凭据如何到达上游。除非连接已在 `auth.headers` 中声明 `Authorization`，运行时 **必须** 按下表处理：

| `auth_mode` | 请求效果 |
|-------------|----------|
| `none`、`database_dsn` | 不注入 HTTP 认证头。 |
| `basic` | `Authorization: Basic base64(username:password)`。 |
| `api_key` | Manifest **必须** 在 `auth.headers` 或 `auth.query_params` 中显式放置凭据（通常引用 `${credentials.KEY}`）。运行时 **不得** 猜测头名或任取一个凭据键；两者都未声明时执行失败。 |
| `oauth2`、`oauth2_cc`、`two_step`、`jwt` | 使用保存的 `access_token`（或 `token`）作为 `Authorization: Bearer <token>`。 |
| `oauth1`、`aws_sigv4`、`app`、`custom` | 宿主定义签名/注入方式；只有宿主在适配器文档中写明时才符合规范。 |

### 8.3 CHECK 语义

CHECK 时运行时 **必须**：

1. 按连接的 `auth_mode` 建立会话。  
2. 若存在 `check`，插值 `check.path` 与 `check.headers`（§9），对路径替换值做 URL 编码，执行检查请求并按点路径提取 profile 字段。  
3. 成功时返回可 JSON 序列化的对象，且包含 `ok: true`。

若 `check` 缺失，运行时 **应当** 不访问上游而直接返回 `ok: true`；这类连接只是 **已声明**，并未 **已验证**，宿主 **可以** 在 UI/审计中区分。

失败 **必须** 以错误形式返回；宿主 **可以** 记审计日志。

### 8.4 `ConfigFieldSpec`

| 字段 | 说明 |
|------|------|
| `key`、`label` | **必填** |
| `input_type` | `text`、`password`、`number`、`boolean`、`select`、`textarea`、`json` |
| `required`、`secret` | 布尔；`secret` 字段 **应当** 在宿主侧加密存储 |
| `default`、`placeholder`、`description`、`enum`、`pattern` | 可选 |

### 8.5 `OAuth2DialectSpec`

| 字段 | 说明 |
|------|------|
| `authorization_url` | 可选；授权码模式通常需要 |
| `token_url` | **必填** |
| `refresh_token_url`、`scopes`、`scope_separator` | 可选 |
| `token_endpoint_auth_method` | `client_secret_basic`、`client_secret_post`、`none` |
| `token_request_format` | `form` 或 `json` |
| `pkce_s256` | 是否使用 PKCE S256 |
| `authorization_params`、`token_params` | 额外参数 |
| `token_response_envelope` | 非标准 token JSON 嵌套路径 |

### 8.6 `TwoStepAuthSpec`

| 字段 | 说明 |
|------|------|
| `token_url` | **必填** |
| `method` | `POST` 或 `GET` |
| `body_format` | `form` 或 `json` |
| `token_params`、`token_headers` | 换票请求 |
| `token_response_path` | 默认 `access_token` |
| `token_expires_in_ms` | 可选 TTL 提示 |

### 8.7 `CheckEndpointSpec`

| 字段 | 默认 | 说明 |
|------|------|------|
| `method` | `GET` | `GET` 或 `POST` |
| `path` | — | **必填** 路径模板；按 §9 插值并做 URL 编码 |
| `headers` | `{}` | 额外头 |
| `account_id_path` | `id` | 响应中的点路径 |
| `display_name_path` | `name` | 展示名点路径 |
| `scopes_path` | — | 可选；已授予 scope |

### 8.8 `RateLimitQuotaSpec`

| 字段 | 说明 |
|------|------|
| `name` | 配额桶名（默认 `default`） |
| `remaining_header`、`reset_header`、`limit_header`、`retry_after_header` | 响应头名称（仅提示） |

---

## 9. 插值

运行时 **必须** 在 `auth` 与执行器模板中支持下列占位符：

| 占位符 | 来源 | 说明 |
|--------|------|------|
| `{{config.KEY}}` | Connection 的 `connection_config`，其次缺失的 `action_params` | **规范性模板写法**；连接值优先（§9.1）。 |
| `${credentials.KEY}` | Connection 密钥 | 除非显式声明，**不得** 出现在路径中。 |
| `{{external_id}}` | MUTATE 目标主键 | 保留名。 |
| `{{patch}}` | MUTATE 变更集 | 保留名。 |
| `{{KEY}}` | Procedure INVOKE 参数 | 用于 procedure 的 path/body 模板；不用于连接 scope。 |

### 9.1 优先级

1. **`connection_config`** 对它定义的每个键都是权威来源。  
2. **`action_params`** / 宿主 scope **可以** 填补 `connection_config` 未定义的键。  
3. 保留值（`external_id`、`patch`）由原语调用提供。

运行时 **不得** 允许 `action_params` 覆盖来自 `connection_config` 的值。否则调用方（包括智能体）可以改写连接的 `owner`、`repo`、租户或数据库 scope，从而重定向请求。

### 9.2 编码

- 替换进 URL **路径** 的值 **必须** 按 RFC 3986 做百分号编码。值中的 `/`、`?`、`#`、`%` **不得** 增加路径层级或查询/片段分隔符。值为 `.` 或 `..` 时 **必须** 拒绝；仅做百分号编码不够，因为 URL 解析器会在解码后归一化点段。  
- 替换进请求头与 JSON body 的值不做百分号编码。  
- 作为结构化映射交给 HTTP 客户端的查询参数由客户端编码，不由模板引擎编码。  
- `base_url` 参与插值，但不做路径编码。

### 9.3 未解析占位符

占位符未解析时，运行时 **必须** 让调用失败，**不得** 静默替换为空字符串。若某占位符永远无法由连接提供，**建议** 在加载时就失败。

### 9.4 `{{patch}}` body 约定

- 当整个 body 模板恰为 `{"patch": "{{patch}}"}` 时，表示“用变更集作为 **整个** 顶层 body”。  
- 在其他位置，`{{patch}}` 解析为变更集对象；例如 `{"fields": "{{patch}}"}` 得到 `{"fields": {…}}`。

---

## 10. 运行时原语

对运行时的规范性要求。宿主 HTTP/MCP 方法名均为资料性。

一次 **原语调用** 须能确定：

1. **Provider** — Manifest 的 `service`。  
2. **Connection** — 使用哪组已保存凭据/配置。  
3. **Action** — `action_id`，对应 `actions[].id`。  
4. **原语** — DISCOVER、LIST、MUTATE、INVOKE 之一。  
5. **Operation** — 仅 MUTATE：`create` \| `update` \| `upsert` \| `delete`。  
6. **载荷** — `action_params`、变更集、游标、`limit` 等（见下表）。

宿主 **不得** 要求配置账本/本体 mapping 后 LIST 才能成功（§10.4）。

### 10.1 通用输入

- Provider `service`。  
- 已解析的 **Connection**。  
- Entity 或 procedure 的 `action_id`（CHECK 除外）。

BOCP 不定义 ACL；宿主 **必须** 在调用原语前做访问控制。

### 10.2 CHECK

- **输出：** 成功时含 `ok: true` 的 profile 对象。

### 10.3 DISCOVER（仅 entity）

| 输入 | 要求 |
|------|------|
| `action_id` | **必填**（entity 的 `id`） |
| `scope` | 宿主定义（如外表名、容器 id） |
| `action_params` | 可选 |

- **输出：** `primary_key`、`fields` 数组。若 Manifest 未声明静态字段且没有 SQL `discover` operation，`fields` 为 `[]`；REST 动态发现属于宿主扩展。

### 10.4 LIST（仅 entity）

| 输入 | 要求 |
|------|------|
| `action_id` | **必填** |
| `scope` | 当执行器需要时由宿主传入（如 SQL `external_table`） |
| `cursor` | 可选 **增量水位**（不是分页游标） |
| `limit` | 可选；本次调用返回记录数的上限 |
| `action_params` | 可选；只填补缺失的 scope 键 |

- **输出：** `records`、可选 `next_cursor_value`、`has_more`。

LIST 语义：

1. 运行时 **可以** 内部连续请求多个上游页；达到 `limit` 或上游耗尽时 **必须** 停止。`paginator.page_size` 只是每页提示，不是调用上限。  
2. `next_cursor_value` 是 **增量水位**（宿主根据 `cursor_field` / 返回记录推导），**不是** 内部页游标；不可得时 **可以** 为 `null`。  
3. 宿主确认上游耗尽时 `has_more` 为 `false`；在达到 `limit` 但未确认耗尽时，宿主 **可以** 保守地返回 `true`。  
4. 记录通过 `operations.records` 提取；该路径缺失时，整个响应体即记录集合。

LIST **必须** 在无宿主账本配置时仍有明确语义（可直接拉上游数据）。

### 10.5 MUTATE（仅 entity）

| 输入 | 要求 |
|------|------|
| `action_id` | **必填** |
| `operation` | `create` \| `update` \| `upsert` \| `delete` |
| 目标键 + 变更集 | `external_id` 是单标量；`create` 省略 |
| `scope` | 执行器需要时传入 |
| `action_params` | 可选；只填补缺失的 scope 键 |

- **输出：** 由宿主定义；**应当** 在可能时返回变更后记录。

`external_id` 无法表达复合 `primary_key`。复合键的 v2 Manifest **不得** 依赖 `{{external_id}}` 做 MUTATE；需要宿主扩展（例如额外的 `action_params` 路径占位符）并在宿主文档中说明。

### 10.6 INVOKE（仅 procedure）

| 输入 | 要求 |
|------|------|
| `action_id` | **必填**（procedure 的 `id`） |
| `arguments` | 对象 |

- **输出：** JSON 值或空成功对象。

### 10.7 错误与上限（资料性）

BOCP **不** 强制全局错误信封。运行时 **应当** 映射上游错误且 **不** 泄露密钥、对 `limit` 设合理默认并文档化行为。

---

## 11. 符合性

### 11.1 Manifest

Bundle **符合** 当且仅当：

1. 校验为 `ConnectorManifest` v2.0。  
2. 满足第 5 节布局规则。  
3. 每条 `auth` 含第 8 节要求的子对象。  
4. 每条 entity 声明 `list`；所有非 `x-` operation 键在封闭集合内（§7.2）。  
5. 每条 procedure 的 `rest.operations` 恰好只有 `invoke`（§7.3）。  
6. 除 `x-` 扩展外没有未声明字段（§3）。

### 11.2 能力等级（资料性）

| 等级 | 要求 |
|------|------|
| **catalog** | 含 `auth`；`actions` 可为空 |
| **readable** | ≥1 个 entity 含 `rest.operations.list` 或 `sql.operations.list` |
| **writable** | 任意 entity 的 MUTATE operation，或任意 procedure |

### 11.3 运行时

运行时 **符合** 当其对所支持 Manifest 中的所有 action 实现第 10 节，遵守第 9 节（含优先级与路径编码），并拒绝含未知 operation 键或非法执行器形状的 Manifest。

---

## 12. 安全考虑

1. Manifest **禁止** 包含真实凭据。  
2. 宿主 **必须** 保护密钥与 OAuth token；运行时 **不得** 在日志中输出已解析的密钥值。  
3. MUTATE 与 INVOKE **应当** 受策略门控。  
4. Manifest 视为可信配置；未签名的第三方 Bundle 风险更高。  
5. 宿主 **必须** 对由 `base_url` 派生的出站主机做 allowlist 或等价校验以防 SSRF，并且 **不得** 跟随到非 allowlist 主机的重定向。  
6. 宿主 **应当** 限制响应大小与请求时间，并执行文档化的 `limit` 上限。  
7. 路径占位符值 **必须** 按 §9.2 编码或拒绝；调用方 **不得** 通过 `action_params` 改变请求目标。  
8. `action_params` **不得** 覆盖 `connection_config` scope（§9.1）。

---

## 13. IANA 考虑

无。未来修订 **可以** 注册媒体类型；在此之前宿主扩展使用 `x-` 命名空间。

---

## 14. 参考文献

### 14.1 规范性

- **BOCP-SCHEMA** — `basis/domain/integration/manifest_schema.py`  
- **RFC2119**、**RFC8174** — BCP 14 关键词  

### 14.2 资料性

- **RFC6749** — OAuth 2.0  
- **Basis-DM** — [data-model.md](../data-model.md) §18  
- **Basis-Connectors** — [runtime.zh.md](runtime.zh.md)  

---

## 15. 修订历史

| 日期 | 变更 |
|------|------|
| 2026-10-20 | **v2.0 规范性澄清**（线上版本号不变）：封闭 operation 键集与强制 `list`；procedure 恰好 `invoke`；`api_key` 必须显式放置；连接级插值优先级；URL 路径编码与未解析占位符报错；LIST limit/分页契约；`spec.openapi` 可选；`x-` 扩展命名空间；SSRF/重定向要求。 |
| 2026-10 | **BOCP v2.0** — `operations` 模型；§1.6 读者指南、附录 D 教程；§4.3.1 双消费者。 |

---

## 附录 A. Operation 标识符

宿主 **应当** 在策略、审计、遥测中使用稳定的逻辑 id（非 MCP 工具名）：

| 模式 | 示例 |
|------|------|
| `{service}.{entity.id}.list` | `github.repositories.list` |
| `{service}.{entity.id}.discover` | `postgres.table_records.discover` |
| `{service}.{entity.id}.{write}` | `github.issues.create` |
| `{service}.{procedure.id}` | `acme.search_codes` |

以上为资料性约定，**不是** Manifest 必填字段。Basis 参考宿主中 `action_policy.entities` 可引用类似键（见 [runtime.zh.md](runtime.zh.md)）。

---

## 附录 B. 模式索引

| 类型 | 作用 |
|------|------|
| `ConnectorManifest` | v2 根对象 |
| `EntityActionSpec`、`ProcedureActionSpec` | `actions[]` 元素 |
| `RestEntityExecutorSpec`、`RestOperationSpec` | REST `operations` |
| `SqlEntityExecutorSpec` | SQL `operations` |
| `PaginatorSpec`、`RestIncrementalSpec` | 分页与增量 LIST |
| `AuthSpec`、`ConfigFieldSpec`、`OAuth2DialectSpec` 等 | 第 8 节认证 |
| `StreamFieldSpec` | 实体静态字段 |

---

## 附录 C. GitHub 示例

权威文件：`basis/domain/integration/providers/github.yaml`。构建：`scripts/connectors/build_connector_manifests.py`。

### C.1 完整 Manifest（`connector.yaml`）

```yaml
version: '2.0'
service: github
display_name: GitHub
description: GitHub repositories, issues, pull requests, and organization members.
categories:
- Developer Tools
- Engineering
homepage_url: https://github.com
docs_url: https://docs.github.com/en/rest
auth:
- auth_mode: oauth2
  base_url: https://api.github.com
  oauth2:
    authorization_url: https://github.com/login/oauth/authorize
    token_url: https://github.com/login/oauth/access_token
    scopes:
    - repo
    - read:org
    - read:user
  check:
    path: /user
    display_name_path: login
- auth_mode: api_key
  base_url: https://api.github.com
  headers:
    Authorization: Bearer ${credentials.personal_access_token}
  credentials:
  - key: personal_access_token
    label: Personal Access Token
    input_type: password
    secret: true
  check:
    path: /user
    display_name_path: login
actions:
- kind: entity
  id: repositories
  display_name: Repositories
  cursor_field: updated_at
  default_label_field: full_name
  fields:
  - name: id
    data_type: integer
    nullable: false
    primary_key: true
  - name: full_name
    nullable: false
  - name: description
  - name: html_url
  - name: language
  - name: stargazers_count
    data_type: integer
  - name: updated_at
    data_type: datetime
  rest:
    operations:
      list:
        method: GET
        path: /user/repos
        pagination:
          type: page
          limit_param: per_page
          page_request_param: page
- kind: entity
  id: issues
  display_name: Repository Issues
  cursor_field: updated_at
  default_label_field: title
  fields:
  - name: id
    data_type: integer
    nullable: false
    primary_key: true
  - name: number
    data_type: integer
    nullable: false
  - name: title
    nullable: false
  - name: state
  - name: body
  - name: html_url
  - name: updated_at
    data_type: datetime
  rest:
    operations:
      list:
        method: GET
        path: /repos/{{config.owner}}/{{config.repo}}/issues
        query:
          state: all
        pagination:
          type: page
          limit_param: per_page
          page_request_param: page
        incremental:
          param: since
      update:
        method: PATCH
        path: /repos/{{config.owner}}/{{config.repo}}/issues/{{external_id}}
        body:
          patch: '{{patch}}'
      create:
        method: POST
        path: /repos/{{config.owner}}/{{config.repo}}/issues
        body:
          patch: '{{patch}}'
spec:
  protocol: rest
  openapi: openapi.yaml

```

以下各小节将上述片段对应到 BOCP 原语（`version: '2.0'`；两条 entity，无重复的 create-issue procedure）。

### C.2 认证

两条 `auth`（`oauth2` 与 `api_key`）共用 CHECK：`GET /user`，从响应提取 `login` 等 profile 字段。访问令牌与 PAT **只** 存在宿主 Connection 中，不出现在 Manifest。

### C.3 Entity `repositories`

静态 `fields` 可供 DISCOVER 直接返回。`rest.operations.list` 指向 `GET /user/repos` 并配置 `page` 分页 → 运行时 **LIST** 原语。

### C.4 Entity `issues`

`rest.operations` 声明 `list`、`create`、`update` 三条线上操作；编译后映射 **LIST** / **MUTATE**，无需再单独建 create-issue **procedure**（避免同一上游效果重复定义）。body `{"patch": "{{patch}}"}` 使用 §9.4 约定：变更集成为整个请求体。`owner` / `repo` 来自 `connection_config`；`action_params` 只能在其缺失时补充，不能覆盖。

### C.5 `spec`

`openapi.yaml` 是可选附件，因为 `spec.openapi` 显式命名了它才存在。**执行** 不读取该 OpenAPI 的 path 定义，只读 `actions[].rest.operations`。若写 `spec: {protocol: rest}` 而不写 `openapi` 字段，则不需要附件文件。

---

## 附录 D. 教程：从零到一次 LIST 调用

资料性端到端教程（GitHub）。HTTP/MCP 路径名因宿主而异；Basis 参考实现见 [runtime.zh.md](runtime.zh.md)。

### D.1 角色

| 角色 | 职责 |
|------|------|
| Connector 作者 | 编写 `providers/github.yaml`（附录 C） |
| 宿主运维 | 加载目录、平台允许列表 |
| 终端用户 | 在工作区创建 **Connection** |
| 消费者 | UI、批任务、智能体，调用 **原语** |

### D.2 Manifest 概念（GitHub `issues`）

附录 C 中 `issues` 表示：「某 `owner`/`repo` 下的仓库 Issue 集合」。

- **`fields`** — 宿主可在 DISCOVER 中直接返回，无需再请求 GitHub metadata。  
- **`operations.list`** — `GET /repos/{{config.owner}}/{{config.repo}}/issues` → **LIST**。  
- **`create` / `update`** — **MUTATE**；body `{"patch": "{{patch}}"}` 按 §9.4 把变更集作为整个顶层 body。

YAML 中 **没有** token；认证只在 `auth` 段声明字段形态。路径替换值在发送前做 URL 编码（§9.2）。

### D.3 用户创建 Connection（示例）

```json
{
  "service": "github",
  "auth_type": "api_key",
  "credentials": { "personal_access_token": "…" },
  "connection_config": { "owner": "acme-corp", "repo": "api" }
}
```

### D.4 CHECK（建议）

运行时：**CHECK** `service=github`，`connection_name=default`。宿主执行 `check.path`（`GET /user`），返回含 `ok: true` 的 profile。失败则先修正凭据再 LIST。

`connection_config` 中的 `owner` / `repo` 是该连接的不可变 scope；`action_params` 只能填补未定义的键（§9.1）。

### D.5 LIST issues（运行时输入）

| 输入 | 值 |
|------|-----|
| `service` | `github` |
| `action_id` | `issues` |
| 原语 | LIST（Basis MCP：`primitive: list`） |
| `action_params` | `{ "owner": "acme-corp", "repo": "api" }`（若未写入 `connection_config`） |
| `limit` | 可选；本次调用返回记录数的上限 |

**输出（概念）：** `{ "records": [ … ], "next_cursor_value": "…", "has_more": false }`，记录形状与 GitHub API 及静态 `fields` 一致。

宿主可以为满足 `limit` 连续请求多个 GitHub 页；`next_cursor_value` 是供后续同步使用的增量水位，不是分页游标（§10.4）。

### D.6 MUTATE create / update

| 输入 | create | update |
|------|--------|--------|
| `operation` | `create` | `update` |
| `changes` | `{ "title": "…", "body": "…" }` | 任意可 PATCH 字段 |
| `external_id` | 省略 | issue **number**（字符串） |
| `action_params` | owner/repo scope | 同左 |

### D.7 智能体（Basis MCP，资料性）

Basis 提供 **通用** MCP 工具，并按 manifest `actions[]` **展开**为具名工具（同一运行时，YAML 不重复定义 operation）：

| 形态 | 命名 | 说明 |
|------|------|------|
| 通用 | `invoke_connector_primitive` | 显式传 `service`、`action_id`、`primitive` 等 |
| 展开 | `connector_{service}__{action_id}__{suffix}` | `suffix` 为 `list`、`discover`、`invoke` 或 `mutate_{create\|update\|upsert\|delete}` |

`tools/list` 按工作区过滤：受 provider 允许列表与 `action_policy.entities` 约束；某原语为 `disabled`（如 `github:issues.list`）时对应展开工具不会出现在列表中。

通用示例：

```json
{
  "name": "invoke_connector_primitive",
  "arguments": {
    "service": "github",
    "action_id": "issues",
    "primitive": "list",
    "connection_name": "default",
    "action_params": { "owner": "acme-corp", "repo": "api" },
    "limit": 50
  }
}
```

展开等价调用：

```json
{
  "name": "connector_github__issues__list",
  "arguments": {
    "connection_name": "default",
    "action_params": { "owner": "acme-corp", "repo": "api" },
    "limit": 50
  }
}
```

HTTP 等价：`POST /api/v1/workspaces/{workspace_id}/connectors/connections/github/default/invoke-primitive`，JSON body 字段与上表一致。

### D.8 账本路径

同步任务内部可调用 **同一** LIST，再把行写入内部账本；mapping 表为 **宿主数据**，不在 Manifest 中。

### D.9 SQL（`postgres`）

`table_records` + `sql.operations`：`discover` 自省列，`list`/`mutate` 时运行时传 `external_table`。

### D.10 新 Provider 检查清单

1. `version: "2.0"`、`service` 与目录名一致。  
2. 至少一条 `auth`，尽量带 `check`；`api_key` **必须** 显式声明 header 或 query 放置位置。  
3. `actions[]` + 单一 `operations` 映射；每条 entity **必须** 含 `list`，只使用封闭 operation 键。  
4. procedure 的 `rest.operations` 只能含 `invoke`。  
5. 在 `description` 中说明必需的 `action_params`；注意连接配置值不能被每次调用覆盖。  
6. 扩展只用 `x-` 字段；其他未声明字段会被校验拒绝。  
7. 用 `manifest_schema.py` 校验并在宿主中测 CHECK + LIST。
