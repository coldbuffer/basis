---
title: Basis connector runtime (BOCP host)
sidebarTitle: Connectors (Basis)
description: Normative expectations for the Basis BOCP reference host—ledger projection and agent MCP—and known wiring gaps.
---

# Basis connector runtime

This document describes how **Basis** implements [BOCP v2.0](bocp.md) as a **host**. Section [Dual consumers](#dual-consumers-one-manifest) states **required** Basis product behavior; other sections are informative unless marked otherwise.

Non-Basis runtimes are not required to match these HTTP paths or MCP tool names.

---

## Dual consumers (one manifest)

A provider bundle (`connector.yaml`) is authored **once**. The BOCP runtime compiles `actions[].rest.operations` / `sql.operations` into **CHECK**, **DISCOVER**, **LIST**, **MUTATE**, and **INVOKE** (see [bocp.md §10](bocp.md#10-runtime-primitives)).

A complete **Basis host MUST** expose that same runtime on **two first-class bindings**:

| Consumer | Binding | How primitives are reached |
|----------|---------|----------------------------|
| **Ontology / ledger** | `source_table_mappings`, inbound sync, `entity_sync_outbox` writeback | `ConnectorRuntime.read_stream` / `mutate_stream` inside `connector_sync` and approved outbox execution |
| **Agents (MCP)** | Workspace MCP tools (and matching OpenAPI where applicable) | **Direct** Section 10 calls: `service` + `action_id` + primitive + `action_params` / `scope` — **without** requiring mapping rows for LIST |

Examples: GitHub `issues` `rest.operations.list` backs both scheduled sync into the evidence ledger **and** an agent asking for the current issue list via MCP. The manifest does not fork; only the host entry point differs.

Agents **MUST NOT** need a parallel manifest, generated OpenAPI per vendor path, or one MCP tool per YAML operation key. Hosts **SHOULD** expose a small stable primitive surface (or equivalent) rather than only ledger-oriented tools.

**Basis reference host — implementation status**

| Binding | Status |
|---------|--------|
| Ledger / projection | **Shipped** — HTTP `/api/v1/workspaces/{workspace_id}/connectors/*`, MCP `sync_connector_table_mapping`, `propose_entity_writeback`, … |
| Agent primitives | **Shipped** — MCP `invoke_connector_primitive` + per-action `connector_{service}__{action_id}__{suffix}` tools from `tools/list`; HTTP `POST …/invoke-primitive` — same runtime as ledger sync |
| Console UI | **Shipped** — `/workspaces/{workspace_id}/connectors` (`web/src/modules/connectors/`); platform allowlist at `/admin/connectors` |

Policy: `action_policy.entities` keys (e.g. `github:issues.list`, `issues.create`) plus `default_entity_read_mode` / `default_entity_write_mode`. Procedures: `execute_connector_tool` or `primitive: invoke`.

---

## Executors (informative)

Normative manifest shape: `rest.operations` / `sql.operations` ([bocp.md §7](bocp.md#7-actions)). Basis compiles them to internal adapters:

| Executor | Basis adapter | Notes |
|----------|---------------|--------|
| `rest.operations` | `rest_declarative` | `list` → LIST; `create`/`update`/… → MUTATE |
| `sql.operations` | `sql_alchemy` | `discover` with `sql_inspector`; table scope via host `external_table` / `action_params` |

All manifests are validated as BOCP v2.0; no other wire version is accepted.

Basis-specific REST extensions (ignored by other BOCP hosts): `x-basis-dynamic-schema-loader`, `x-basis-record-fields-unwrap-path`, `x-basis-record-filter-jinja`, and `x-basis-partition-router` on an entity action. They preserve adapter features that the v2 wire surface does not standardize.

---

## Code map

| Component | Location |
|-----------|----------|
| Runtime | `basis/domain/integration/runtime.py` |
| REST adapter | `basis/domain/integration/adapters/rest/` |
| SQL adapter | `basis/domain/integration/adapters/sql/` |
| Provider bundles | `basis/domain/integration/providers/` |
| Manifest schema | `basis/domain/integration/manifest_schema.py` |
| Catalog | `basis/domain/integration/catalog.py` |
| Build shipped bundles | `scripts/connectors/build_connector_manifests.py` |

---

## Host APIs

| Surface | Location |
|---------|----------|
| HTTP | `/api/v1/workspaces/{workspace_id}/connectors/*` (see [openapi-v1.md](openapi-v1.md) and live `/openapi/v1.json`) |
| MCP | `basis/application/operations_connectors.py` (`invoke_connector_primitive`, sync, catalog, …) |

Persistence and workspace projection: [data-model.md](../data-model.md) §18.

---

## Validation

```bash
uv run pytest tests/test_bocp_phase1.py -q
```

SQL integration tests (optional env): `tests/test_sql_connector_integration.py`.

---

## Known gaps (informative)

- Regenerate OpenAPI snapshots after route changes: `uv run python scripts/openapi/generate-openapi-v1.py`.

---

## Related

- bocp.md(bocp.md) / bocp.zh.md(bocp.zh.md) — protocol specification
- [product.md](product.md) — connector product architecture
