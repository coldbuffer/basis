<h1 align="center">Basis: Let agents understand real business</h1>

<div align="center">

**Ontology-driven enterprise business semantics layer.**

[![CI](https://github.com/coldbuffer/basis/actions/workflows/ci.yml/badge.svg)](https://github.com/coldbuffer/basis/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](pyproject.toml)
[![Node](https://img.shields.io/badge/node-%3E%3D22-green.svg)](web/package.json)

**English** · [简体中文](./README.zh-CN.md)

</div>

Map documents, databases, and SaaS to **entities, types, and governed facts**. That is the shared meaning layer above raw systems. Run on desktop, self-hosted, or cloud with **OpenAPI v1** and **MCP**. State changes go through review, not silent API calls.

Basis is an open-source stack built on the [Semantica](https://github.com/semantica-agi/semantica) Python SDK. **Business semantics** include mappings, ontologies, rules, and SHACL. They sit on a canonical **evidence ledger**. Graph and search are **rebuildable projections**.

> **Status:** Under active development. APIs may change. Use a pinned release in production.

<p align="center">
  <img src="assets/graph.png" alt="Basis graph workspace: force-directed ledger projection, ontology navigation, temporal scrubber" width="900" style="border-radius: 12px;" />
</p>
<p align="center"><sub>Graph workspace in the Basis studio.</sub></p>

## Table of contents

- [Features](#features)
- [Why Basis](#why-basis)
- [Quick start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [1. Clone and configure API](#1-clone-and-configure-api)
  - [2. Run Web](#2-run-web)
  - [3. Smoke-test in the UI](#3-smoke-test-in-the-ui)
- [Configuration (essentials)](#configuration-essentials)
- [Integration](#integration)
  - [Access tokens](#access-tokens)
  - [OpenAPI (REST)](#openapi-rest)
  - [MCP (JSON-RPC)](#mcp-json-rpc)
- [Development](#development)
- [Deployment](#deployment)
  - [Desktop app](#desktop-app)
  - [Self-hosted](#self-hosted)
  - [Managed cloud](#managed-cloud)
- [Community](#community)
- [License](#license)

## Features

- **Business semantics:** Entities, typed facts, mappings, and ontologies. The unit of meaning is not “another chunk.”
- **Evidence ledger:** Canonical statements and provenance. Graph and vectors are projections you can rebuild.
- **Workspaces:** Document ingest, chunk search (lexical + embeddings), processing jobs, and a review queue.
- **Graph & ontology:** Explorer-style graph UI, vocabulary, SHACL, SPARQL, and ontology hub workflows.
- **Connectors (BOCP):** Shipped providers (e.g. postgres, mysql, github, slack) with inbound sync and governed writeback.
- **Agent APIs:** Workspace-scoped **OpenAPI v1** and **MCP** (`search_chunks`, `find_entities`, connector tools, review ops).
- **Platform:** Users, org SSO (OIDC/SAML optional), workspace roles, API tokens, and audit.

```mermaid
flowchart TB
  subgraph external["External sources"]
    docs["Documents & files"]
    systems["Databases & SaaS · app APIs"]
  end

  subgraph clients["Clients"]
    studio["Web studio"]
    agents["Agents & automation"]
  end

  subgraph apiLayer["basis/interface/http · FastAPI"]
    rest["OpenAPI v1 · REST"]
    mcp["MCP · JSON-RPC over HTTP"]
  end

  ops["Application operations · shared catalog"]

  subgraph platform["Platform"]
    plat["Auth · orgs · SSO · API tokens · audit"]
  end

  subgraph workspace["Workspace"]
    subgraph integration["Application integration"]
      sources["Sources · ingest & processing jobs"]
      connSync["Connectors · inbound sync & mappings"]
      connGw["Connectors · app service gateway"]
    end

    subgraph ontologySvc["Ontology service"]
      hub["Ontology Hub · registry & workflows"]
      govern["SHACL · SPARQL · vocabulary"]
      maps["Mappings · types · reasoning rules"]
    end

    ledger[("Evidence ledger · canonical facts & provenance")]
    review["Review queue · governed writes"]
    graphProj["Graph projection · rebuildable"]
    searchProj["Search projection · lexical + embeddings"]
  end

  docs --> sources
  systems --> connSync
  sources --> ledger
  connSync --> ledger
  connSync -.->|"feeds semantics"| maps
  maps -.->|"aligns meaning"| ledger
  govern -.->|"validates"| ledger
  ledger --> graphProj
  ledger --> searchProj

  agents --> mcp
  mcp --> ops
  ops --> connGw
  connGw -->|"tools & governed calls"| systems
  connGw --> review
  review -->|"approved writeback"| ledger

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

## Why Basis

| | Typical “RAG + raw tools” | **Basis** |
| --- | --- | --- |
| **Read path** | Unverified chunks / ad hoc SQL | Ledger and entities. Graph and search rebuild from the ledger. |
| **Write path** | Ungoverned API calls | Review gates (`remember`, connector writeback, conflicts) |
| **Business semantics** | Prompt labels | Shared entities & types, mappings, ontologies, rules, SHACL, SPARQL |
| **Connectivity** | Per-system glue | BOCP manifests, OpenAPI v1, MCP |
| **Ops** | Many services | API and Web. SQLite for dev, PostgreSQL for production. |

## Quick start

### Prerequisites

- **Python** 3.10–3.13 and [uv](https://docs.astral.sh/uv/)
- **Node.js** ≥ 22 and npm

### 1. Clone and configure API

```bash
git clone https://github.com/coldbuffer/basis.git
cd basis
cp .env.example .env
uv sync --extra dev
uv run basis
```

API listens on `http://127.0.0.1:8090` by default.

### 2. Run Web

```bash
cp web/.env.example web/.env
cd web && npm install && npm run dev
```

Open `http://127.0.0.1:5173` and register. The **first user** becomes platform admin.

In-app product docs: **`http://127.0.0.1:5173/docs`** · API explorer: **`http://127.0.0.1:8090/swagger`** · live spec: **`http://127.0.0.1:8090/openapi/v1.json`**.

### 3. Smoke-test in the UI

1. Create a workspace.
2. In **Sources**, paste or upload a short text file and wait for processing.
3. Open **Graph** or **Search** for that workspace.

This path is **self-hosted** dev. For the **desktop app** or **managed cloud**, see [Deployment](#deployment).

## Configuration (essentials)

| Variable | Default | Purpose |
| --- | --- | --- |
| `BASIS_HOST` / `BASIS_PORT` | `127.0.0.1` / `8090` | API bind |
| `BASIS_DATA_DIR` | `./data` | SQLite, blobs, graph JSON |
| `BASIS_DATABASE_URL` | *(unset → SQLite)* | PostgreSQL for production |
| `BASIS_API_URL` | `http://127.0.0.1:8090` | Web dev proxy (`web/.env`) |
| `BASIS_MCP_MAX_INFLIGHT` | `32` | Concurrent MCP JSON-RPC requests |
| `BASIS_MCP_TIMEOUT_SECONDS` | `60` | Per-request MCP timeout (seconds) |

Full list: [.env.example](.env.example).

**PostgreSQL:** `docker compose -f compose.postgres.yml up -d`, then  
`BASIS_DATABASE_URL=postgresql://basis:basis@127.0.0.1:5432/basis` (host port **5432**).

**Backups:** `./scripts/ops/backup_basis_data.sh` (SQLite) or `./scripts/ops/backup_basis_postgres.sh` (Postgres).

## Integration

Basis exposes two integration surfaces for agents and automation. **OpenAPI v1** is REST over HTTP. **MCP** is JSON-RPC over HTTP to the same workspace operations. They share one **operation catalog** and the same **workspace access tokens**.

In the studio, open **Integration** (`/workspaces/{workspace_id}/integration`) for MCP URL, Cursor config, workspace OpenAPI explorer, and token management.

### Access tokens

1. In the workspace, go to **Integration → Access tokens** (workspace admin).
2. Create a token and copy the secret. Use `Authorization: Bearer <token>` on every integration call.
3. Choose a **scope** (`read`, `write`, or `admin`) that matches what your agent needs.

MCP and OpenAPI both use this header. Point clients at the **Basis API** (for example `http://127.0.0.1:8090`), not the Vite dev port (`5173`).

### OpenAPI (REST)

**Live specs** (while `uv run basis` is up):

| Document | URL |
| --- | --- |
| Full v1 | `http://127.0.0.1:8090/openapi/v1.json` |
| Workspace integration (agents) | `http://127.0.0.1:8090/openapi/v1/workspaces.json` |
| Platform (auth, orgs, settings) | `http://127.0.0.1:8090/openapi/v1/platform.json` |

**Swagger UI:** `http://127.0.0.1:8090/swagger` (full API). The Integration **OpenAPI** tab scopes Try it out to the current workspace.

**HTTP base:** `http://127.0.0.1:8090/api/v1/workspaces/{workspace_id}/…` with the bearer token above.

Example workspace read:

```bash
curl -sS "http://127.0.0.1:8090/api/v1/workspaces/YOUR_WORKSPACE_ID" \
  -H "Authorization: Bearer YOUR_WORKSPACE_TOKEN"
```

Generate clients from `workspaces.json` or call paths by `operationId`. Snapshots for CI live under `openapi/` in the repo.

### MCP (JSON-RPC)

Use **Integration → MCP** in the studio for the endpoint URL, tool list, and copy-paste client config. The transport is JSON-RPC 2.0 over `POST /api/v1/workspaces/{workspace_id}/mcp`.

**Cursor / `mcp.json`** (replace workspace id and token):

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

Tune server-side limits with `BASIS_MCP_MAX_INFLIGHT` and `BASIS_MCP_TIMEOUT_SECONDS` (see [Configuration (essentials)](#configuration-essentials)).

## Development

```bash
uv run pytest -q
uv run lint-imports --config importlinter.ini
cd web && npm run typecheck && npm test
cd web && CI=1 npm run test:e2e   # optional, Playwright + API
```

**Pre-push gate (optional, per clone):** run tests before `git push`.

```bash
./scripts/dev/setup-git-hooks.sh   # once per clone → core.hooksPath=.githooks
./scripts/dev/pre-push-check.sh    # same checks manually
```

Emergency bypass: `git push --no-verify` or `BASIS_SKIP_PREPUSH=1 git push`. Full CI still runs on GitHub.

Layout for contributors is `basis/interface`, `application`, `domain`, and `infra`. See [AGENTS.md](AGENTS.md). Script index: [scripts/README.md](scripts/README.md).

**Schema migrations:** Alembic (`alembic.ini`); runtime and CLI use `BASIS_DATABASE_URL` when set. See [basis/infra/tooling/db/README.md](basis/infra/tooling/db/README.md).

## Deployment

One product stack (API + studio). Pick **where** it runs. The **OpenAPI v1** and **MCP** contracts are the same across modes.

### Desktop app

**Local client** (Electron) for a single machine: API sidecar + studio, data under `~/.basis`, optional **no-login** desktop profile for personal use.

- **Develop:** `cd desktop && npm install && npm run dev`. See [desktop/README.md](desktop/README.md) for packaging and macOS/Windows builds.
- **Profile:** `BASIS_DEPLOYMENT_PROFILE=desktop` (see `profiles/profile.desktop.yaml`).

Do not run a dev API and an installed desktop app at once. They share `~/.basis/basis.db`.

### Self-hosted

**You operate** the stack on your network or cloud VM (air-gapped OK). You control platform login, org SSO, workspaces, and backups under your policies.

- **Try locally:** [Quick start](#quick-start) (`uv run basis` + `npm run dev`, SQLite).
- **Production:** PostgreSQL (`compose.postgres.yml`), set `BASIS_DATABASE_URL`, TLS in front of API/Web, and pin a release. See [Configuration (essentials)](#configuration-essentials).

### Managed cloud

**Basis-hosted SaaS** provides multi-tenant signup with operations and upgrades on our side. Integrate agents against the same workspace **HTTP/MCP** endpoints with your issued tokens.

Hosted availability is rolling out. For access or pilots, open a [GitHub Issue](https://github.com/coldbuffer/basis/issues) and describe your use case.

## Community

- **Bug reports & features:** [GitHub Issues](https://github.com/coldbuffer/basis/issues)
- **Security vulnerabilities:** [SECURITY.md](SECURITY.md) (please do not file public issues)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## License

[Apache License 2.0](LICENSE).
