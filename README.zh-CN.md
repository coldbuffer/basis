<h1 align="center">Basis：让智能体读懂真实业务</h1>

<div align="center">

**本体驱动的企业业务语义层。**

[![CI](https://github.com/coldbuffer/basis/actions/workflows/ci.yml/badge.svg)](https://github.com/coldbuffer/basis/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](pyproject.toml)
[![Node](https://img.shields.io/badge/node-%3E%3D22-green.svg)](web/package.json)

[English](./README.md) · **简体中文**

</div>

将文档、数据库与 SaaS 对齐为**实体、类型与可治理事实**。这是源系统之上的共享语义层。可在桌面、自托管或云端运行，通过 **OpenAPI v1** 与 **MCP** 对外集成。状态变更须经审核，而非静默 API 调用。

Basis 是基于 [Semantica](https://github.com/semantica-agi/semantica) Python SDK 构建的开源技术栈。**业务语义**包括映射、本体、规则与 SHACL。它们落在**规范证据账本**之上。图与搜索为**可重建投影**。

> **状态：** 仍在积极开发，接口可能变动。生产环境请固定发布版本。  
> **v0.1** 对应当前已实现功能；连接器规模扩充放在后续版本 — 见 [RELEASE.md](RELEASE.md)。

<p align="center">
  <img src="assets/graph.png" alt="Basis 图谱工作区：力导向图、本体导航、时间轴回放" width="900" style="border-radius: 12px;" />
</p>
<p align="center"><sub>Basis 工作台中的图谱工作区。</sub></p>

## 目录

- [能力概览](#能力概览)
- [为什么选择 Basis](#为什么选择-basis)
- [快速开始](#快速开始)
  - [环境](#环境)
  - [1. 克隆并启动 API](#1-克隆并启动-api)
  - [2. 启动 Web](#2-启动-web)
  - [3. 冒烟验证](#3-冒烟验证)
- [配置（常用）](#配置常用)
- [集成](#集成)
  - [访问令牌](#访问令牌)
  - [OpenAPI（REST）](#openapirest)
  - [MCP（JSON-RPC）](#mcpjson-rpc)
- [开发](#开发)
- [部署方式](#部署方式)
  - [桌面客户端](#桌面客户端)
  - [自托管](#自托管)
  - [托管云（SaaS）](#托管云saas)
- [社区](#社区)
- [许可证](#许可证)

## 能力概览

- **业务语义：** 实体、类型化事实、映射与本体。语义单元不是「又一坨切片」。
- **证据账本：** 陈述与溯源。图与向量为可重建投影。
- **工作区：** 文档入库、切片检索（词法 + 向量）、处理任务与审核队列。
- **图谱与本体：** Explorer 风格图工作区、词表、SHACL、SPARQL 与 Ontology Hub 工作流。
- **连接器（BOCP）：** 内置 provider（如 postgres、mysql、github、slack），支持入向同步与受控写回。
- **智能体接口：** 工作区级 **OpenAPI v1** 与 **MCP**（`search_chunks`、`find_entities`、连接器工具、审核操作等）。
- **平台：** 用户、组织 SSO（可选 OIDC/SAML）、工作区角色、API 令牌与审计。

```mermaid
flowchart TB
  subgraph external["外部数据源"]
    docs["文档与文件"]
    systems["数据库、SaaS 与应用 API"]
  end

  subgraph clients["客户端"]
    studio["Web 工作台"]
    agents["智能体与自动化"]
  end

  subgraph apiLayer["basis/interface/http · FastAPI"]
    rest["OpenAPI v1 · REST"]
    mcp["MCP · JSON-RPC over HTTP"]
  end

  ops["应用操作层 · 共用 catalog"]

  subgraph platform["平台"]
    plat["认证 · 组织 · SSO · API 令牌 · 审计"]
  end

  subgraph workspace["工作区"]
    subgraph integration["应用集成"]
      sources["来源 · 入库与处理任务"]
      connSync["连接器 · 入向同步与映射"]
      connGw["连接器 · 应用服务网关"]
    end

    subgraph ontologySvc["本体服务"]
      hub["Ontology Hub · 注册与工作流"]
      govern["SHACL · SPARQL · 词表"]
      maps["映射 · 类型 · 推理规则"]
    end

    ledger[("证据账本 · 规范事实与溯源")]
    review["审核队列 · 受治理写入"]
    graphProj["图投影 · 可重建"]
    searchProj["搜索投影 · 词法 + 向量"]
  end

  docs --> sources
  systems --> connSync
  sources --> ledger
  connSync --> ledger
  connSync -.->|"汇入语义"| maps
  maps -.->|"对齐语义"| ledger
  govern -.->|"校验"| ledger
  ledger --> graphProj
  ledger --> searchProj

  agents --> mcp
  mcp --> ops
  ops --> connGw
  connGw -->|"工具调用与受治理访问"| systems
  connGw --> review
  review -->|"核准写回"| ledger

  studio --> rest
  agents --> rest
  rest --> ops
  ops --> plat
  ops --> sources
  ops --> connSync
  ops --> hub
  ops --> govern
  ops --> maps
  ops --> ledger
  ops --> graphProj
  ops --> searchProj
  ops --> review

  classDef canonical fill:#f4f4f5,stroke:#18181b,stroke-width:2px
  classDef projection fill:#fafafa,stroke:#71717a,stroke-dasharray: 5 3
  class ledger canonical
  class graphProj,searchProj projection
```

## 为什么选择 Basis

| | 典型「RAG + 裸工具」 | **Basis** |
| --- | --- | --- |
| **读取路径** | 未校验切片 / 临时 SQL | 账本与实体。图与搜索由账本重建。 |
| **写入路径** | 无治理的 API 调用 | 审核闸口（`remember`、连接器写回、冲突处理） |
| **业务语义** | 提示词标签 | 共享实体与类型、映射、本体、规则、SHACL、SPARQL |
| **连接** | 各系统手写胶水 | BOCP manifest、OpenAPI v1、MCP |
| **运维** | 多组件拼凑 | API 与 Web。开发用 SQLite，生产用 PostgreSQL。 |

## 快速开始

### 环境

- **Python** 3.10–3.13、[uv](https://docs.astral.sh/uv/)
- **Node.js** ≥ 22、npm

### 1. 克隆并启动 API

```bash
git clone https://github.com/coldbuffer/basis.git
cd basis
cp .env.example .env
uv sync --extra dev
uv run basis
```

默认 `http://127.0.0.1:8090`。

### 2. 启动 Web

```bash
cp web/.env.example web/.env
cd web && npm install && npm run dev
```

浏览器打开 `http://127.0.0.1:5173`，**首个注册用户**为平台管理员。

产品文档 **`http://127.0.0.1:5173/docs`** · 接口探索 **`http://127.0.0.1:8090/swagger`** · 在线规范 **`http://127.0.0.1:8090/openapi/v1.json`**。

### 3. 冒烟验证

1. 创建工作区  
2. **Sources** 粘贴或上传短文，等待处理完成  
3. 打开该工作区的 **Graph** 或 **Search**

以上属于**自托管**开发路径。**桌面客户端**与**托管云**见 [部署方式](#部署方式)。

## 配置（常用）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `BASIS_HOST` / `BASIS_PORT` | `127.0.0.1` / `8090` | API 监听 |
| `BASIS_DATA_DIR` | `./data` | SQLite、blob、图 JSON |
| `BASIS_DATABASE_URL` | 空则 SQLite | 生产建议 PostgreSQL |
| `BASIS_API_URL` | `http://127.0.0.1:8090` | Web 代理（`web/.env`） |
| `BASIS_MCP_MAX_INFLIGHT` | `32` | MCP JSON-RPC 并发请求上限 |
| `BASIS_MCP_TIMEOUT_SECONDS` | `60` | 单次 MCP 请求超时（秒） |

详见 [.env.example](.env.example)。

**PostgreSQL：** `docker compose -f compose.postgres.yml up -d`，  
`BASIS_DATABASE_URL=postgresql://basis:basis@127.0.0.1:5432/basis`（宿主机端口 **5432**）。

**备份：** `./scripts/ops/backup_basis_data.sh`（SQLite）或 `./scripts/ops/backup_basis_postgres.sh`（Postgres）。

## 集成

Basis 为智能体与自动化提供两种集成方式。**OpenAPI v1** 是 HTTP REST。**MCP** 是对同一套工作区操作的 HTTP JSON-RPC。二者共用**操作目录**与**工作区访问令牌**。

在工作台打开 **Integration**（`/workspaces/{workspace_id}/integration`），可查看 MCP 地址、Cursor 配置、工作区 OpenAPI 探索器并管理令牌。

### 访问令牌

1. 进入工作区 **Integration → Access tokens**（需工作区管理员）。
2. 创建令牌并复制密钥。每次集成请求使用 `Authorization: Bearer <token>`。
3. 按需要选择 **scope**（`read`、`write` 或 `admin`）。

MCP 与 OpenAPI 使用同一请求头。客户端应指向 **Basis API**（例如 `http://127.0.0.1:8090`），而非 Vite 开发端口（`5173`）。

### OpenAPI（REST）

**在线规范**（在 `uv run basis` 运行时）：

| 文档 | URL |
| --- | --- |
| 完整 v1 | `http://127.0.0.1:8090/openapi/v1.json` |
| 工作区集成（智能体） | `http://127.0.0.1:8090/openapi/v1/workspaces.json` |
| 平台（登录、组织、设置） | `http://127.0.0.1:8090/openapi/v1/platform.json` |

**Swagger UI：** `http://127.0.0.1:8090/swagger`（全量 API）。Integration 页的 **OpenAPI** 标签可将 Try it out 限定在当前工作区。

**HTTP 前缀：** `http://127.0.0.1:8090/api/v1/workspaces/{workspace_id}/…`，并携带上述 Bearer 令牌。

示例（读取工作区）：

```bash
curl -sS "http://127.0.0.1:8090/api/v1/workspaces/YOUR_WORKSPACE_ID" \
  -H "Authorization: Bearer YOUR_WORKSPACE_TOKEN"
```

可用 `workspaces.json` 生成客户端，或按 `operationId` 调用路径。仓库 `openapi/` 下有供 CI 对照的快照。

### MCP（JSON-RPC）

在工作台 **Integration → MCP** 查看端点 URL、工具列表并复制客户端配置。传输方式为 JSON-RPC 2.0，请求 `POST /api/v1/workspaces/{workspace_id}/mcp`。

**Cursor / `mcp.json`**（替换工作区 id 与令牌）：

```json
{
  "mcpServers": {
    "basis-workspace": {
      "url": "http://127.0.0.1:8090/api/v1/workspaces/YOUR_WORKSPACE_ID/mcp",
      "headers": {
        "Authorization": "Bearer <your-api-token>"
      }
    }
  }
}
```

服务端并发与超时见 `BASIS_MCP_MAX_INFLIGHT`、`BASIS_MCP_TIMEOUT_SECONDS`（[配置（常用）](#配置常用)）。

## 开发

```bash
uv run pytest -q
uv run lint-imports --config importlinter.ini
cd web && npm run typecheck && npm test
cd web && CI=1 npm run test:e2e   # 可选，Playwright + API
```

贡献者包结构为 `basis/interface`、`application`、`domain`、`infra`。见 [AGENTS.md](AGENTS.md)。

## 部署方式

同一套产品栈（API + 工作台）。选择**运行位置**即可。各模式下 **OpenAPI v1** 与 **MCP** 契约一致。

### 桌面客户端

**本机 Electron 应用**内嵌 API 与工作台，数据目录为 `~/.basis`。桌面配置可**免登录**，适合个人单机使用。

- **开发：** `cd desktop && npm install && npm run dev`，打包与 macOS/Windows 说明见 [desktop/README.md](desktop/README.md)。
- **配置：** `BASIS_DEPLOYMENT_PROFILE=desktop`（见 `profiles/profile.desktop.yaml`）。

勿与已安装的桌面版同时跑开发 API。二者共用 `~/.basis/basis.db`。

### 自托管

由**你方运维**（内网、专有云或隔离环境均可）。平台账号、组织 SSO、工作区与备份策略由你方自控。

- **本地试用：** [快速开始](#快速开始)（`uv run basis` + `npm run dev`，SQLite）。
- **生产：** PostgreSQL（`compose.postgres.yml`）、配置 `BASIS_DATABASE_URL`、反向代理 TLS 并固定发布版本。见 [配置（常用）](#配置常用)。

### 托管云（SaaS）

**Basis 托管的多租户服务**由我方负责注册、运维与升级。智能体仍通过工作区 **HTTP/MCP** 与令牌集成。

托管服务逐步开放。如需访问或试点，请提交 [GitHub Issue](https://github.com/coldbuffer/basis/issues) 并说明使用场景。

## 社区

- **缺陷与功能请求：** [GitHub Issues](https://github.com/coldbuffer/basis/issues)
- **安全漏洞：** [SECURITY.md](SECURITY.md)（请勿公开提交 issue）
- **贡献：** [CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## 许可证

[Apache License 2.0](LICENSE).
