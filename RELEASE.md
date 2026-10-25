# Release plan

**Policy:** **v0.1** ships everything that is **implemented and tested in this repository today**. Capabilities on the connector roadmap (OpenConnector / Airbyte scale-up), deferred ADRs, and excluded product bets are **explicitly out of scope** for v0.1 and land in **v0.2+**.

Normative feature IDs live in local `docs/features.md` and status in `docs/progress.md` (not in git). This file is the **public** release contract for tags `v0.1.*` and `desktop-v0.1.*`.

English summary below; [简体中文](#v01-发版范围) follows.

---

## Versioning

| Tag | Artifact | Notes |
|-----|----------|--------|
| `v0.1.x` | Docker image (GHCR), GitHub Release (draft → manual publish) | Patch: fixes only, same scope as v0.1.0 |
| `desktop-v0.1.x` | Electron installers | Same codebase slice as server `v0.1.x` |
| `v0.2.0`+ | TBD | First release that **expands** the connector catalog / embed product sign-off (see [Later](#later-not-in-v01)) |

---

## v0.1 scope (ship now)

### Platform & workspace

- Auth (register/login/session), users, orgs, workspace CRUD, roles, API tokens, audit
- Platform settings and **model catalog** (Chat / embed credentials for LLM extract)
- OIDC + SAML HTTP surface (enterprise SSO); production IdP sign-off is optional per deployment

### Knowledge & processing

- Document / file ingest, processing jobs, chunking, **LLM-only extract** (requires configured Chat model)
- Chunk search (lexical + embeddings), ledger reads, review queue (merge, import, mapping, remember, conflicts)
- Sources: webhook, http_poll, GitHub raw (frozen set); ingest job APIs and console UX

### Graph, ontology, reasoning

- Graph explorer UI, projection rebuild, search / neighbors / paths, temporal `at` / diff / staging merge flows
- Ontology Hub, vocabulary, SHACL, SPARQL read, mappings
- Rules CRUD, `POST .../reasoning/run`, derived facts on the graph
- Governance decisions, alerts (SSE), governor passes (incl. graph dedup)

### Agent integration

- **OpenAPI v1** + **MCP** (static core tools + connector tools from shipped manifests)
- Workspace integration console (OpenAPI export, MCP wiring); **no in-browser Playground chat** (replaced by MCP + Review)

### Connectors (BOCP) — *as implemented today*

- BOCP v2 runtime: check, discover, sync, invoke-primitive, writeback via review
- **Shipped provider set** in-repo (e.g. postgres, mysql, github, qq_mail) — not hundreds of connectors
- Workspace `/connectors` (catalog, mappings, policy, runs) and platform `/admin/connectors` allowlist
- Dual-mode connections (workspace + `end_user` / embed) — engineering baseline per internal connector ROADMAP phase 1

### Desktop (0.1.x)

- Electron app with bundled API sidecar, local `~/.basis` data dir, desktop profile (see `desktop/README.md`)
- Unsigned / Gatekeeper notes documented for macOS

### Operations

- SQLite default; PostgreSQL supported
- Backup scripts: `scripts/ops/backup_basis_data.sh`, `scripts/ops/backup_basis_postgres.sh`

---

## Later (not in v0.1)

Do **not** promise these in v0.1 release notes or marketing. Target **v0.2+** unless noted.

### Connector roadmap (main gap)

| Track | v0.1 | Later |
|-------|------|--------|
| OpenConnector migration (auth + procedures, N≥10 beta/GA connectors) | Partial — only **shipped** manifests | **v0.2** milestone |
| Airbyte-scale **entity/stream** catalog merge | Not started | **v0.3+** |
| Product sign-off: embed demo providers, catalog visibility policy, MCP embed gates | Open items | **v0.2** checklist |

### Product / ADR deferred

- ADR 0007 Part B — full canvas merge studio (use graph-diff + staging + review today)
- Markdown node resource persistence
- Multi-instance realtime WS (Redis pub/sub); single worker / sticky sessions OK for v0.1
- Agent Memory browser (`F-MEM-*`) — excluded
- Semantica graph as standalone npm package (M5-02) — excluded

### Maturity caveats (honest in v0.1 notes)

- APIs may change; pin `v0.1.x` in production
- Connector catalog is **early** — sufficient for BOCP reference host, not a full integration marketplace
- Enterprise SSO: code paths exist; **production IdP validation** is deployment-specific

---

## v0.1 发版范围

**原则：** **0.1 版本 = 当前仓库里已经实现、有测试支撑的全部能力**；连接器路线图里尚未做完的规模与产品签收项，一律放到 **0.2 及以后**。

### 0.1 包含（与上文 English 一致）

- 平台与工作区、文库与处理、图/本体/推理/治理
- OpenAPI v1 + MCP（无控制台 Playground 对话，走 MCP + 审核）
- **BOCP 连接器运行时** + 仓库内**已发货**的少数 Provider（非全量目录）
- Desktop 0.1.x 安装包与 Docker `v0.1.x` 镜像

### 0.1 不包含（后续版本）

- OpenConnector 大批量迁移、Airbyte entity 全量合成
- 连接器 GA 名单扩大、embed 产品决策收口（规划 **0.2**）
- 画布合并 B 方案、Memory 产品、多实例 WS 等（见 `docs/progress.md` §4 Deferred）

### 发版操作

1. CI green on `main`
2. Tag `v0.1.x` / `desktop-v0.1.x` → workflows build artifacts
3. **Draft** GitHub Release → verify → **Publish** → promote Docker `latest` (see `release-docker-promote-latest.yml`)

---

_Last updated: 2026-10-25 — v0.1 = current tree; connector scale-up deferred to v0.2+._
