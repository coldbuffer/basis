---
title: BOCP v2.0 — connector manifests
sidebarTitle: BOCP spec
description: Normative BOCP v2.0 specification plus a reader's guide for newcomers (manifest, primitives, operations, hosts).
---

# Basis Open Connector Protocol (BOCP) Version 2.0

| | |
|---|---|
| **Document** | BOCP v2.0 |
| **Status** | Basis Standards Track (normative for Basis releases) |
| **Wire format** | YAML manifest + this specification |
| **Schema companion** | `basis/domain/integration/manifest_schema.py` (Pydantic v2) |
| **Related** | [runtime.md](runtime.md) (Basis host; non-normative) |

---

## Abstract

This document defines the **Basis Open Connector Protocol (BOCP)**: a **consumer-neutral**, **transport-pluggable** manifest for external **Providers**—how to **authenticate**, and which **actions** a conforming **runtime** may execute.

A manifest declares **`auth`** and **`actions`**. Each action is an **entity** (DISCOVER, LIST, optional MUTATE) or a **procedure** (INVOKE). Reaching upstream systems is expressed only through **`rest`** or **`sql`** executor blocks (`operations` maps) interpreted by the host implementation layer. v2 defines execution only for `rest` and `sql`; `graphql` / `grpc` are attachment hints, not executable executors.

Runtimes expose **CHECK**, **DISCOVER**, **LIST**, **MUTATE**, and **INVOKE**. Connections, policy, scheduling, and workspace projection are **host bindings** and MUST NOT appear in `connector.yaml`.

Wire `version` **MUST** be `"2.0"`. Other versions are not accepted.

**New readers:** start with the [BOCP guide](/docs/bocp-guide), then [Section 1.6](#16-readers-guide-start-here) and [Appendix D](#appendix-d-tutorial-from-zero-to-a-list-call) in this specification.

---

## Status of This Document

Structured in the style of IETF RFCs (simplified [RFC 7841](https://www.rfc-editor.org/info/rfc7841)). BOCP is **not** an IETF standards-track protocol unless separately published.

Implementations claiming BOCP v2.0 conformance **MUST** satisfy Section 11 (Conformance).

---

## Table of Contents

1. [Introduction](#1-introduction)（includes [§1.6 Reader's guide](#16-readers-guide-start-here)）  
2. [Terminology](#2-terminology)  
3. [Notation](#3-notation)  
4. [Protocol overview](#4-protocol-overview)  
5. [Provider bundle](#5-provider-bundle)  
6. [Connector manifest](#6-connector-manifest)  
7. [Actions](#7-actions)  
8. [Authentication](#8-authentication)  
9. [Interpolation](#9-interpolation)  
10. [Runtime primitives](#10-runtime-primitives)  
11. [Conformance](#11-conformance)  
12. [Security considerations](#12-security-considerations)  
13. [IANA considerations](#13-iana-considerations)  
14. [References](#14-references)  
15. [Revision history](#15-revision-history)  
Appendix A. [Operation identifiers](#appendix-a-operation-identifiers)  
Appendix B. [Schema index](#appendix-b-schema-index)  
Appendix C. [GitHub example](#appendix-c-github-example)  
Appendix D. [Tutorial: from zero to a LIST call](#appendix-d-tutorial-from-zero-to-a-list-call)  

---

## 1. Introduction

### 1.1 Requirements language

The key words "**MUST**", "**MUST NOT**", "**REQUIRED**", "**SHALL**", "**SHALL NOT**", "**SHOULD**", "**SHOULD NOT**", "**RECOMMENDED**", "**NOT RECOMMENDED**", "**MAY**", and "**OPTIONAL**" in this document are to be interpreted as described in BCP 14 [[RFC2119](https://www.rfc-editor.org/info/rfc2119)] [[RFC8174](https://www.rfc-editor.org/info/rfc8174)] when, and only when, they appear in all capitals.

### 1.2 Problem statement

Integrations need a portable description of **how to authenticate** and **what operations exist** on an external product, without encoding whether the caller is a UI, an agent, or a batch job, and without tying the manifest to a single wire technology.

Vendor API descriptions (for example OpenAPI) rarely cover connection forms, multiple auth modes, and a uniform model for listing and mutating records. BOCP supplies a small manifest and a fixed primitive set; **how** bindings execute is delegated to the host.

### 1.3 Goals

1. **Consumer neutrality** — Manifest data MUST NOT encode ledger, ontology, or MCP-specific fields.  
2. **Transport pluggability** — Manifests are not locked to a single upstream protocol. Entity executors are currently `rest` or `sql`; `graphql` / `grpc` are attachment hints and do not define execution semantics.  
3. **Simple surface** — One array `actions[]` with `kind: entity | procedure`.  
4. **Extensibility** — Executor `operations` values and host adapters MAY evolve when backward compatible.  
5. **Upstream preservation** — Vendors (GitHub, Postgres, …) do not “speak BOCP”; only your **host** reads the manifest and calls their real APIs.

### 1.4 Non-goals

BOCP does **not** specify: secret storage, OAuth client registration, token refresh scheduling, provider allowlists, audit retention, graph/ledger mapping, or which primitives are exposed over HTTP, MCP, or CLI. Those are **host bindings** (Section 4.3).

### 1.5 Relationship to other specifications

| Specification | Relationship |
|-----------------|--------------|
| **OpenAPI 3.x** | MAY be attached under `spec` for documentation; normative execution uses `actions[].rest.operations` / `sql.operations`, not vendor path items, unless a host explicitly consumes the attachment. The attachment is **OPTIONAL**; a host MUST NOT assume `openapi.yaml` exists unless `spec.openapi` names it. |
| **OAuth 2.0** [[RFC6749](https://www.rfc-editor.org/info/rfc6749)] | `oauth2` auth mode embeds URLs; token storage is host-specific. |
| **JSON Schema** | MAY describe procedure `input_schema`; INVOKE validation is host-defined. |

### 1.6 Reader's guide (start here)

This section is for readers who have **never** seen BOCP before. Normative rules elsewhere still use BCP 14 keywords; here we explain the ideas in plain language.

#### 1.6.1 What problem BOCP solves

Products expose different APIs (REST, SQL, GraphQL, …), different auth flows (OAuth, API keys, database DSNs), and different payload shapes. Application code often re-implements the same patterns: “connect”, “list rows”, “update a row”, “call this RPC”.

BOCP is a **small YAML manifest** per external product (**provider**) that answers:

1. **How can a user connect?** (forms, OAuth URLs, headers — Section 8)  
2. **What logical objects exist?** (the `actions[]` catalog — Section 7)  
3. **How does the host reach upstream for each operation?** (`rest.operations` or `sql.operations` — Sections 7.5–7.6)

The manifest is **not** where passwords live. Users store **connections** (secrets + options) in the **host** at runtime.

#### 1.6.2 Three layers (do not confuse them)

| Layer | What it is | Example |
|-------|------------|---------|
| **Manifest** | Shipped `connector.yaml` for provider `github` | Declares `auth` + `actions[].rest.operations.list.path` |
| **Connection** | Per-tenant saved link to upstream | OAuth token or PAT; `connection_config: { owner, repo }` |
| **Primitive call** | One runtime operation | LIST on `action_id: issues` with `action_params` |

```
  Author ships          User / admin saves        App or agent calls
  connector.yaml   →    Connection (secrets)  →   CHECK / LIST / MUTATE / …
```

#### 1.6.3 BOCP vs vendor OpenAPI

| | Vendor OpenAPI | BOCP manifest |
|---|----------------|---------------|
| **Focus** | HTTP paths, schemas, servers | Auth + stable **business actions** |
| **Caller model** | Per-endpoint clients | Five **primitives** (Section 10) |
| **Secrets** | Usually out of band | `auth` + `credentials` **fields** (not values) |
| **Agents / sync** | Not specified | Same manifest for ledger sync **and** direct LIST |

You MAY attach OpenAPI under `spec.openapi` as documentation; execution still follows `operations` unless the host documents otherwise.

#### 1.6.4 The five primitives (runtime vocabulary)

These are the **only** execution verbs a conforming runtime must understand. Hosts expose them via HTTP, MCP, jobs, etc.

| Primitive | Applies to | Plain meaning |
|-----------|------------|-----------------|
| **CHECK** | Connection | “Are credentials valid?” (e.g. `GET /user`) |
| **DISCOVER** | Entity action | “What fields does this object have?” |
| **LIST** | Entity action | “Return a batch of records” (pagination / cursor) |
| **MUTATE** | Entity action | `create` / `update` / `upsert` / `delete` on one record |
| **INVOKE** | Procedure action | Arbitrary RPC (search, send message, …) |

**Entity** actions ( `kind: entity` ) use DISCOVER, LIST, MUTATE. **Procedure** actions ( `kind: procedure` ) use INVOKE.

#### 1.6.5 The `actions[]` catalog

`actions` is a **flat list** of things this provider offers. Each item has:

- `kind`: `entity` or `procedure`  
- `id`: stable name used in every primitive call (`action_id`) — Section 7.2.2  
- Metadata: `display_name`, `fields`, …  
- **Exactly one executor block**: `rest` **or** `sql`  
- Inside the executor: a single map **`operations`**

There is **no** separate top-level `list:` / `writes:` in v2. All wire details live under `operations`:

```yaml
rest:
  operations:
    list:    { method: GET,  path: /… }
    create:  { method: POST, path: /…, body: … }
    update:  { method: PATCH, path: /…/{{external_id}}, body: … }
```

Operation **keys** (`list`, `create`, …) tell the runtime which primitive to run. They are not a second manifest format.

#### 1.6.6 Scope: `action_params` and templates

Paths often need context (GitHub `owner` / `repo`, SQL table name). BOCP uses:

- **`connection_config`** on the connection (defaults for a saved link; **immutable scope**)  
- **`action_params`** on each primitive call (per-request scope; fills **missing** keys only)  
- Templates in paths: `{{config.owner}}`, `{{external_id}}`, `{{patch}}` — Section 9

Caller-supplied `action_params` **MUST NOT** override a `connection_config` key of the same name. The manifest stays the same; only missing parameters change per customer or per call.

#### 1.6.7 Two kinds of consumers (one manifest)

The same `connector.yaml` supports:

1. **Knowledge / ledger hosts** — map LIST results into an internal graph (scheduled sync, writeback approval).  
2. **Agents** — call LIST / MUTATE directly without configuring an internal “table mapping”.

BOCP requires LIST to work **without** ledger configuration (Section 10.4). How the host surfaces MCP tool names is **not** in the manifest ([runtime.md](runtime.md) describes one reference host).

#### 1.6.8 How to read the rest of this document

| If you want to… | Read |
|-----------------|------|
| Ship a provider bundle | Sections 5–8, Appendix C–D |
| Call a runtime from your app | Section 10, Appendix D |
| Implement a host | Sections 4, 10–11, [runtime.md](runtime.md) |
| Policy / telemetry ids | Appendix A |

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Provider** | External product identified by `service`. |
| **Bundle** | `providers/{service}.yaml` and optional sidecar files (e.g. `{service}.openapi.yaml`) in the same directory. |
| **Manifest** | Parsed `{service}.yaml` conforming to `ConnectorManifest` (v2). |
| **Connection** | Runtime tuple: `auth_type`, `connection_config`, `credentials` (not in manifest). |
| **Action** | One catalog entry: entity or procedure. |
| **Entity action** | Action with `kind: entity`; supports DISCOVER, LIST, optional MUTATE. |
| **Procedure action** | Action with `kind: procedure`; supports INVOKE. |
| **Executor** | `rest` or `sql` block on an action; contains `operations`. |
| **Operation key** | Name inside `operations` (e.g. `list`, `create`); maps to a primitive (Section 7.4). |
| **Primitive** | CHECK, DISCOVER, LIST, MUTATE, INVOKE (Section 10). |
| **`action_id`** | The action’s `id` field; passed on every primitive call. |
| **`action_params`** | Per-call scope object; fills **missing** `{{config.*}}` keys but never overrides `connection_config` (Section 9). |
| **Host** | Application that loads manifests, stores connections, exposes HTTP/MCP, enforces policy. |
| **Runtime** | Library that executes primitives given manifest + connection (no UI). |
| **Host binding** | Host-specific feature (MCP tool names, ledger mappings) **not** stored in the manifest. |
| **Extension field** | Any object member whose key starts with `x-`; ignored by conforming runtimes but preserved by loaders. |

---

## 3. Notation

- Manifest serialization **MUST** be YAML 1.2 unless the host documents otherwise; Basis uses UTF-8 YAML.  
- Field names in prose use `monospace` and match manifest keys.  
- `service` pattern: `^[a-z0-9][a-z0-9_-]*$`.  
- Manifest `version` for this document **MUST** be `"2.0"`.  
- Types follow the JSON data model unless noted.
- Any object member whose key starts with `x-` is an **extension**; all other undeclared members are invalid.
- Entity `rest.operations` keys are closed to `list`, `create`, `update`, `upsert`, `delete`; `sql.operations` additionally allows `discover`; a procedure’s `rest.operations` **MUST** contain exactly `invoke`. Keys starting with `x-` are ignored extensions, not operations.

Authoritative machine-readable schema: `manifest_schema.py`. This document and the schema **SHOULD** be updated together.

---

## 4. Protocol overview

### 4.1 Layers

```
  +------------------+
  |  Host bindings   |  connections, policy, projection, HTTP/MCP/CLI
  +--------+---------+
           |
  +--------v---------+
  |  BOCP runtime    |  CHECK, DISCOVER, LIST, MUTATE, INVOKE
  +--------+---------+
           |
  +--------v---------+
  |  BOCP manifest   |  auth, actions, spec (attachments)
  +--------+---------+
           |
  +--------v---------+
  |  Upstream        |  (implementation-specific)
  +------------------+
```

### 4.2 Primitives and actions

| Action `kind` | Primitives |
|---------------|------------|
| `entity` | DISCOVER, LIST, MUTATE (per `operations` write keys) |
| `procedure` | INVOKE |

CHECK applies to the **connection** (auth), not to a single action id.

Any consumer **MAY** invoke any primitive the runtime exposes; BOCP does not assign primitives to “agent” vs “sync” roles.

The same manifest and runtime **MUST** be usable for both **workspace projection** (for example ledger sync and governed writeback) and **interactive agents** (for example MCP tools that call LIST without prior mapping). The manifest does not choose a consumer; the **host** wires one or more bindings (Section 4.3.1).

### 4.3 Host bindings

Hosts **MAY** implement persistence and APIs described in [data-model.md](../data-model.md) §18. Those artifacts **MUST NOT** appear inside `connector.yaml`.

BOCP does **not** mandate HTTP route names or MCP tool ids. Hosts **SHOULD** expose Section 10 primitives on agent-facing surfaces using stable selectors: `service`, entity or procedure `action_id`, primitive kind (`discover`, `list`, `mutate`, `invoke`), plus host-supplied `action_params` / `scope` (Section 10).

### 4.3.1 Dual consumers (informative)

Product hosts (for example [runtime.md](runtime.md)) typically attach **two parallel bindings** to one BOCP runtime:

| Consumer | Typical host binding | Primitive use |
|----------|----------------------|---------------|
| **Ontology / ledger** | Stream-to-entity mappings, scheduled inbound sync, outbox writeback | LIST / MUTATE during sync and approved outbound changes |
| **Agents (MCP, chat tools)** | Direct primitive APIs on the workspace MCP server and/or OpenAPI | DISCOVER, LIST, MUTATE, INVOKE **without** requiring mapping rows |

Neither binding **MAY** require a second manifest or duplicate operation definitions. Agent LIST **MUST** remain valid with no ledger configuration (Section 10.4).

---

## 5. Provider bundle

### 5.1 Layout

```
providers/
  {service}.yaml
  {service}.openapi.yaml   # optional REST attachment
```

Optional attachment files are referenced from `spec` (Section 6). BOCP v2 does not define attachment semantics beyond “file MUST exist when `spec` requires it”; hosts validate layout at load time.

### 5.2 Loading rules

1. Manifest file name **MUST** be `{service}.yaml` where `service` matches the `service` field inside the file.  
2. Hosts **MUST** reject manifests that fail schema validation.  
3. Hosts **MAY** load bundles read-only at startup.

### 5.3 `ProviderSpecReference` (`spec`)

| Field | Description |
|-------|-------------|
| `protocol` | `rest` (default) \| `sql` \| `graphql` \| `grpc` — **hint for attachments**, not execution semantics. Only `rest` and `sql` have v2 executors. |
| `openapi`, `graphql`, `grpc` | Optional relative paths. A path **MUST** exist when declared; omitting it does **not** imply a default file. |

Execution **MUST** use `actions[].rest` / `actions[].sql` `operations`, not vendor OpenAPI path items, unless a host explicitly consumes attachments. Hosts **MUST NOT** require `openapi.yaml` merely because `protocol: rest` is present.

---

## 6. Connector manifest

| Field | Required | Description |
|-------|----------|-------------|
| `version` | yes | **MUST** be `"2.0"`. |
| `service` | yes | Provider id (Section 3). |
| `display_name` | yes | Catalog name. |
| `description` | no | |
| `categories` | no | String tags. |
| `homepage_url`, `docs_url`, `icon_url` | no | URIs. |
| `spec` | no | Attachment hints (Section 5.3). |
| `auth` | yes | Non-empty `AuthSpec` array (Section 8). |
| `actions` | no | Default `[]`. |

Undeclared fields **MUST NOT** appear on any manifest object, except extension fields whose names start with `x-`. Basis enforces this with a shared base model.

---

## 7. Actions

### 7.1 Discriminator

Each element of `actions[]` **MUST** include `kind`:

- `entity` — `EntityActionSpec`  
- `procedure` — `ProcedureActionSpec`

Action `id` values **MUST** be unique within the provider.

### 7.2 Entity action (`kind: entity`)

Entity metadata is **protocol-neutral**. Wire operations live in exactly one executor block: **`rest`** or **`sql`** (matching the host’s protocol stack).

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Stable id; primitive selector for this entity. |
| `display_name` | yes | Label. |
| `description` | no | |
| `primary_key` | no | Field names; default `["id"]`. |
| `cursor_field` | no | **RECOMMENDED** for incremental LIST. |
| `default_label_field` | no | Display hint. |
| `fields` | no | Static field list for DISCOVER (`StreamFieldSpec`). |
| `rest` | one of | HTTP executor — `operations` map (Section 7.5). |
| `sql` | one of | SQL executor — `operations` map (Section 7.6). |

Every entity **MUST** declare `list` in its executor’s `operations` map. `operations` keys are **closed**:

- REST: `list`, `create`, `update`, `upsert`, `delete`.
- SQL: the same keys plus `discover`.

A loader **MUST** reject unknown non-`x-` operation keys; silently ignoring them would make a manifest appear to support operations it does not. A write-only entity is not representable in v2 — model the call as a procedure instead.

If `fields` is empty and the executor declares no dynamic discovery operation, DISCOVER returns an empty `fields` array. REST metadata discovery is a host extension (for example under an `x-` field); SQL discovery uses `operations.discover`.

#### 7.2.1 `StreamFieldSpec` (entity fields)

| Field | Description |
|-------|-------------|
| `name` | **REQUIRED** |
| `data_type` | `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `json`, `array` |
| `nullable`, `primary_key` | Booleans |
| `fk_target_stream` | Optional hint (same provider entity `id`) |
| `description` | Optional |

#### 7.2.2 `action_id` naming (informative)

Within a provider, `id` **SHOULD** be a short `snake_case` name for the business collection (often plural), for example `issues`, `table_records`. Do **not** prefix with `service` (use manifest `service`). Scope parameters (owner, repo, table name) belong in `action_params` / connection config, not in `id`. Host logical ids remain `{service}.{action_id}.{operation}` (Appendix A).

### 7.3 Procedure action (`kind: procedure`)

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Stable id for INVOKE. |
| `name` | yes | Short name (distinct from `id` allowed). |
| `display_name` | yes | Label. |
| `description` | no | **RECOMMENDED** when hosts expose MCP. |
| `input_schema`, `output_schema` | no | JSON Schema fragments. |
| `annotations` | no | `read_only_hint`, `destructive_hint`, `idempotent_hint` |
| `required_scopes` | no | OAuth scope hints for hosts |
| `rest` | yes | `rest.operations` containing **exactly** the `invoke` key. |

v2 defines no procedure executor other than `rest`; a SQL or GraphQL procedure is not conformant.

### 7.4 Authoring rules

1. **One operations map** — All HTTP (or SQL) wire operations for an entity live under `rest.operations` or `sql.operations`; do not split `list` and `writes` at the manifest root.  
2. **Closed key vocabulary** — Key `list` → LIST; `create` \| `update` \| `upsert` \| `delete` → MUTATE; procedure `invoke` → INVOKE. No other keys are allowed.  
3. **No duplicate effects** — Do not model the same upstream call as both an entity operation and a procedure. This rule is a **SHOULD NOT**; hosts MAY warn at load time, but cannot always detect semantic duplicates.

### 7.5 REST executor (`entity.rest` / `procedure.rest`)

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

| Field | Description |
|-------|-------------|
| `method` | **REQUIRED** `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `path` | **REQUIRED** path or template; substituted values are URL-encoded (Section 9) |
| `query`, `headers` | Optional; values are interpolated but not URL-encoded as a whole |
| `body` | Optional JSON template (mutations). `{"patch": "{{patch}}"}` as the **entire** body means “use the change set as the top-level body”; a nested `{{patch}}` string resolves to the change-set object. |
| `pagination` | `PaginatorSpec` (typically on `list`) |
| `incremental` | `{ param: <name>, inject_into: query \| body \| header }` watermark (LIST; default `query`) |
| `records` | JSON path segments to the row array. Omitted or empty means the **whole response body** is the record collection. |

Operation keys are validated per entity/procedure; see Sections 7.2–7.4.

#### 7.5.2 `PaginatorSpec` (informative)

| Field | Description |
|-------|-------------|
| `type` | `none`, `cursor`, `offset`, `page`, `link` |
| `page_size` | Default page size hint |
| `limit_param` | Request param for max rows |
| `inject_into` | `query`, `body`, or `header` |
| `cursor_request_param`, `cursor_response_path` | Cursor pagination |
| `offset_request_param` | Offset pagination |
| `page_request_param` | Page-number pagination (e.g. GitHub `page`) |
| `link_header_rel`, `link_response_path` | Link header or JSON next link |
| `stop_condition_jinja` | Optional stop expression |

`page_size` is a per-request hint, not the LIST result limit. A host MAY continue fetching upstream pages until it reaches the primitive’s `limit` or upstream exhaustion; it **MUST** stop at `limit`. See Section 10.4 for the LIST output contract.

Hosts compile `rest.operations` into the HTTP client / REST adapter layer ([runtime.md](runtime.md)).

### 7.6 SQL executor (`entity.sql`)

```yaml
sql:
  operations:
    discover: { type: sql_inspector }
    list: {}
    create: {}
    update: {}
```

Operation values are interpreted by the SQL/ORM executor (e.g. SQLAlchemy); allowed keys are `list`, `discover`, `create`, `update`, `upsert`, `delete`. `list` is **REQUIRED**. `list` / `create` / `update` keys map to LIST / MUTATE; `discover` is the SQL schema-introspection operation. Table scope is supplied at runtime (host `external_table`) and MUST be validated/quoted by the executor as an identifier.

---

## 8. Authentication

Each `AuthSpec` describes one **auth mode**. The connection’s `auth_type` **MUST** match exactly one entry at runtime.

### 8.1 `auth_mode` values

`none`, `api_key`, `basic`, `two_step`, `oauth2`, `oauth2_cc`, `oauth1`, `jwt`, `aws_sigv4`, `app`, `database_dsn`, `custom`.

### 8.2 Common fields

| Field | Requirement |
|-------|-------------|
| `base_url` | **REQUIRED** for REST connections; MUST NOT duplicate paths that belong in action bindings. |
| `headers`, `query_params` | **MAY** include interpolated secrets (Section 9). |
| `connection_config`, `credentials` | `ConfigFieldSpec` form definitions. |
| `oauth2` | **REQUIRED** when `auth_mode` is `oauth2` or `oauth2_cc`. |
| `two_step` | **REQUIRED** when `auth_mode` is `two_step`. |
| `check` | **OPTIONAL**; used by CHECK when present. |
| `quotas` | **OPTIONAL** rate-limit metadata. |

#### 8.2.1 Request auth injection (normative)

The auth mode determines **how credentials reach upstream**. A runtime **MUST** apply the following unless the connection already declares an `Authorization` header in `auth.headers`.

| `auth_mode` | Request effect |
|-------------|----------------|
| `none`, `database_dsn` | No HTTP auth headers are injected. |
| `basic` | `Authorization: Basic base64(username:password)`. |
| `api_key` | The manifest **MUST** place the credential explicitly in `auth.headers` or `auth.query_params`, normally via `${credentials.KEY}`. Runtimes **MUST NOT** guess a header name or pick an arbitrary credential key; execution fails when neither placement is declared. |
| `oauth2`, `oauth2_cc`, `two_step`, `jwt` | Use the stored `access_token` (or `token`) as `Authorization: Bearer <token>`. |
| `oauth1`, `aws_sigv4`, `app`, `custom` | Host-defined signing/injection. These modes are conformant only if the host documents the behavior in its adapter documentation. |

### 8.3 CHECK semantics

On CHECK, the runtime **MUST**:

1. Establish a session for the connection’s auth mode.  
2. If `check` is present, interpolate `check.path` and `check.headers` (Section 9), URL-encode substituted path values, run the check request, and extract profile fields (dot paths).  
3. Return a JSON-serializable object including `ok: true` on success.

If `check` is absent, the runtime **SHOULD** return `ok: true` without an upstream request; such a connection is *declared*, not *verified*, and hosts **MAY** report that distinction.

Failures **MUST** surface as errors; hosts **MAY** audit.

### 8.4 `ConfigFieldSpec`

| Field | Description |
|-------|-------------|
| `key`, `label` | **REQUIRED** |
| `input_type` | `text`, `password`, `number`, `boolean`, `select`, `textarea`, `json` |
| `required`, `secret` | Booleans; secrets **SHOULD** be encrypted at rest on the host |
| `default`, `placeholder`, `description`, `enum`, `pattern` | Optional |

### 8.5 `OAuth2DialectSpec`

| Field | Description |
|-------|-------------|
| `authorization_url` | Optional; required for authorization-code flows |
| `token_url` | **REQUIRED** |
| `refresh_token_url`, `scopes`, `scope_separator` | Optional |
| `token_endpoint_auth_method` | `client_secret_basic`, `client_secret_post`, `none` |
| `token_request_format` | `form` or `json` |
| `pkce_s256` | Boolean |
| `authorization_params`, `token_params` | Extra parameters |
| `token_response_envelope` | Non-standard token JSON nesting |

### 8.6 `TwoStepAuthSpec`

| Field | Description |
|-------|-------------|
| `token_url` | **REQUIRED** |
| `method` | `POST` or `GET` |
| `body_format` | `form` or `json` |
| `token_params`, `token_headers` | Exchange request |
| `token_response_path` | Default `access_token` |
| `token_expires_in_ms` | Optional TTL hint |

### 8.7 `CheckEndpointSpec`

| Field | Default | Description |
|-------|---------|-------------|
| `method` | `GET` | `GET` or `POST` |
| `path` | — | **REQUIRED** path template; interpolated and URL-encoded (Section 9) |
| `headers` | `{}` | Extra |
| `account_id_path` | `id` | Dot path into response |
| `display_name_path` | `name` | Dot path into response |
| `scopes_path` | — | Optional granted scopes |

### 8.8 `RateLimitQuotaSpec`

| Field | Description |
|-------|-------------|
| `name` | Quota bucket (default `default`) |
| `remaining_header`, `reset_header`, `limit_header`, `retry_after_header` | Response header names (hints only) |

---

## 9. Interpolation

Runtimes **MUST** support these placeholders in templates accepted by `auth` and executor blocks:

| Placeholder | Source | Notes |
|-------------|--------|-------|
| `{{config.KEY}}` | Connection `connection_config`, then missing `action_params` | **Normative template form.** Connection values win (Section 9.1). |
| `${credentials.KEY}` | Connection secrets | MUST NOT be exposed in paths unless explicitly declared. |
| `{{external_id}}` | MUTATE target key | Reserved name. |
| `{{patch}}` | MUTATE change set | Reserved name. |
| `{{KEY}}` | Procedure INVOKE arguments | Used in procedure path/body templates; not for connection scope. |

### 9.1 Precedence

1. **`connection_config`** is authoritative for every key it defines.  
2. **`action_params`** / host scope MAY fill keys that `connection_config` does not define.  
3. Reserved values (`external_id`, `patch`) are supplied by the primitive call.

A runtime **MUST NOT** allow `action_params` to replace a value sourced from `connection_config`. Otherwise a caller—including an agent—could change the connection’s `owner`, `repo`, `tenant`, or database scope and redirect the request.

### 9.2 Encoding

- Values substituted into a URL **path** **MUST** be percent-encoded per RFC 3986. `/`, `?`, `#`, and `%` in a value **MUST NOT** be able to add path segments or query/fragment delimiters. A value equal to `.` or `..` **MUST** be rejected; percent-encoding alone is insufficient because URL parsers normalize decoded dot segments.  
- Values substituted into headers and JSON bodies are not percent-encoded.  
- Query parameters passed to the HTTP client as a structured map are encoded by the client, not by the template engine.  
- `base_url` is interpolated but not path-encoded.

### 9.3 Unresolved placeholders

A runtime **MUST** fail the call when a placeholder remains unresolved; it **MUST NOT** silently replace it with an empty string. Failing at load time is **RECOMMENDED** when the placeholder can never be supplied by a connection.

### 9.4 The `{{patch}}` body convention

- A body template that is exactly `{"patch": "{{patch}}"}` means “use the change set as the **entire** top-level body”.  
- In any other position, `{{patch}}` resolves to the change-set object; for example `{"fields": "{{patch}}"}` becomes `{"fields": {…}}`.

---

## 10. Runtime primitives

Normative for runtimes. Host method names are informative.

A **primitive call** always identifies:

1. **Provider** — manifest `service` (e.g. `github`).  
2. **Connection** — which saved credentials / config to use.  
3. **Action** — `action_id` matching `actions[].id`.  
4. **Primitive** — which verb (DISCOVER, LIST, MUTATE, INVOKE).  
5. **Operation** — for MUTATE only: `create` | `update` | `upsert` | `delete`.  
6. **Payload** — `action_params`, `changes` / `patch`, cursors, limits (per table below).

Hosts **MUST NOT** require ledger or ontology configuration for LIST to succeed (Section 10.4).

### 10.1 Common inputs

- Provider `service`.  
- Resolved **Connection**.  
- **Entity** or **procedure** action `id` (except CHECK).

Hosts **MUST** enforce access control before primitives; BOCP does not define ACLs.

### 10.2 CHECK

- **Output:** Profile object with `ok: true` on success.

### 10.3 DISCOVER (entity only)

| Input | Requirement |
|-------|-------------|
| `action_id` | **REQUIRED** (entity `id`) |
| `scope` | Host-defined (e.g. external table name, container id) |
| `action_params` | Optional |

- **Output:** `primary_key`, `fields` array. If the manifest declares no static fields and no SQL `discover` operation, `fields` is `[]`; REST dynamic discovery is a host extension.

### 10.4 LIST (entity only)

| Input | Requirement |
|-------|-------------|
| `action_id` | **REQUIRED** |
| `scope` | Host-defined (e.g. external table name, container id) |
| `cursor` | Optional **incremental watermark** (not a page cursor) |
| `limit` | Optional maximum number of records returned by this call |
| `action_params` | Optional; fills missing scope keys only |

- **Output:** `records`, optional `next_cursor_value`, `has_more`.

LIST semantics:

1. The runtime **MAY** fetch multiple upstream pages internally. It **MUST** stop when it reaches `limit` or upstream exhaustion. `paginator.page_size` is a per-request hint, not the call limit.  
2. `next_cursor_value` is the **incremental watermark** (host-derived from `cursor_field` / returned records), **not** an internal page cursor. It MAY be `null` when no watermark is available.  
3. `has_more` is `false` when the host has confirmed upstream exhaustion. A host **MAY** conservatively return `true` when it stopped at `limit` without confirming exhaustion.  
4. Records are extracted with `operations.records`; when that path is absent, the whole response body is the record collection.

LIST **MUST** be meaningful without host ledger configuration.

### 10.5 MUTATE (entity only)

| Input | Requirement |
|-------|-------------|
| `action_id` | **REQUIRED** |
| `operation` | `create` \| `update` \| `upsert` \| `delete` |
| Target key + change set | `external_id` is a single scalar; omitted for `create` |
| `scope` | When required by the executor |

- **Output:** Host-defined; **SHOULD** return post-change record when available.

`external_id` cannot express a composite `primary_key`. A v2 manifest with a composite key **MUST NOT** rely on `{{external_id}}` for MUTATE; it needs a host extension (for example additional `action_params` path placeholders) documented by that host.

### 10.6 INVOKE (procedure only)

| Input | Requirement |
|-------|-------------|
| `action_id` | **REQUIRED** (procedure `id`) |
| `arguments` | Object |

- **Output:** JSON value or empty success object.

### 10.7 Errors and limits (informative)

BOCP does **not** mandate a global error envelope. Runtimes **SHOULD** map upstream failures without leaking secrets, apply default `limit` caps, and document behavior.

---

## 11. Conformance

### 11.1 Manifest

A bundle **is conformant** when:

1. It validates as `ConnectorManifest` v2.0.  
2. Section 5 layout rules hold.  
3. Each `auth` entry includes required sub-objects (Section 8).  
4. Every entity declares `list`; every non-`x-` operation key is in the closed set (Section 7.2).  
5. Every procedure’s `rest.operations` contains exactly `invoke` (Section 7.3).  
6. Undeclared fields are absent except for `x-` extensions (Section 3).

### 11.2 Classes (informative)

| Class | Requirement |
|-------|-------------|
| **catalog** | `auth` present; actions may be empty |
| **readable** | ≥1 entity with `rest.operations.list` or `sql.operations.list` |
| **writable** | Any entity MUTATE operation (`create` / `update` / `upsert` / `delete`) or any procedure |

### 11.3 Runtime

A runtime **is conformant** when it implements Section 10 for all actions in supported manifests, honors Section 9 (including precedence and path encoding), and rejects manifests with unknown operation keys or invalid executor shapes.

---

## 12. Security considerations

1. Manifests **MUST NOT** contain live credentials.  
2. Hosts **MUST** protect secrets and OAuth tokens; runtimes **MUST NOT** log resolved secret values.  
3. MUTATE and INVOKE **SHOULD** be policy-gated.  
4. Treat manifests as trusted configuration; unsigned third-party bundles increase risk.  
5. Hosts **MUST** validate outbound hosts derived from `base_url` against an allowlist (or equivalent) to prevent SSRF, and **MUST NOT** follow redirects to non-allowlisted hosts.  
6. Hosts **SHOULD** bound response size and request time, and apply documented `limit` caps.  
7. Path placeholder values **MUST** be encoded or rejected as specified in Section 9.2; a caller **MUST NOT** be able to alter the request target through `action_params`.  
8. `action_params` **MUST NOT** override `connection_config` scope (Section 9.1).

---

## 13. IANA considerations

None. A future revision **MAY** register a media type. Until then, host-specific extensions use the `x-` namespace.

---

## 14. References

### 14.1 Normative

- **BOCP-SCHEMA** — `basis/domain/integration/manifest_schema.py`  
- **RFC2119**, **RFC8174** — BCP 14 keywords  

### 14.2 Informative

- **RFC6749** — OAuth 2.0  
- **Basis-DM** — [data-model.md](../data-model.md) §18  
- **Basis-Connectors** — [runtime.md](runtime.md)  

---

## 15. Revision history

| Date | Change |
|------|--------|
| 2026-10-20 | **v2.0 normative clarifications** (wire version unchanged): closed operation-key sets and mandatory `list`; procedure exactly `invoke`; explicit `api_key` placement; connection-scoped interpolation precedence; URL path encoding and unresolved-placeholder failure; LIST limit/pagination contract; optional `spec.openapi`; `x-` extension namespace; SSRF/redirect requirements. |
| 2026-10 | **BOCP v2.0** — `operations` model; §1.6 reader's guide & Appendix D tutorial; §4.3.1 dual consumers. |

---

## Appendix A. Operation identifiers

Hosts **SHOULD** use stable logical ids for policy and telemetry:

| Pattern | Example |
|---------|---------|
| `{service}.{entity.id}.list` | `github.repositories.list` |
| `{service}.{entity.id}.discover` | `postgres.table_records.discover` |
| `{service}.{entity.id}.{write}` | `github.issues.create` |
| `{service}.{procedure.id}` | `acme.search_codes` |

Not required manifest keys.

---

## Appendix B. Schema index

| Type | Role |
|------|------|
| `ConnectorManifest` | Root v2 |
| `EntityActionSpec`, `ProcedureActionSpec` | Actions |
| `RestOperationSpec`, `RestEntityExecutorSpec` | REST `operations` |
| `AuthSpec`, `ConfigFieldSpec`, … | Section 8 |
| `StreamFieldSpec` | Entity static fields |

---

## Appendix C. GitHub example

Informative. Canonical file: `basis/domain/integration/providers/github.yaml`. Regenerate: `scripts/connectors/build_connector_manifests.py`.

### C.1 Complete manifest

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

### C.2 Auth

Two `auth` entries share CHECK `GET /user` → profile `id` / `login`. Tokens live on the host, not in the manifest.

### C.3 Entity `repositories`

Static `fields` → DISCOVER without a dynamic `discover` operation. `rest.operations.list` (GET + `path` + `pagination`) → LIST.

### C.4 Entity `issues`

`rest.operations` defines `list`, `create`, and `update` as HTTP operations (`method`, `path`, `body`, …). The REST executor compiles them to LIST / MUTATE; no separate procedure for create issue. The body `{"patch": "{{patch}}"}` uses the Section 9.4 convention: the change set becomes the entire request body. `owner` / `repo` come from `connection_config`; `action_params` can fill them only when absent, never override them.

### C.5 `spec`

`openapi.yaml` is an optional attachment; it exists here because `spec.openapi` names it. Runtime execution uses `actions[].rest.operations`, not paths from that OpenAPI file. A manifest with `spec: {protocol: rest}` and no `openapi` field needs no attachment file.

---

## Appendix D. Tutorial: from zero to a LIST call

Informative walkthrough using the GitHub provider. Exact HTTP/MCP names depend on the host; [runtime.md](runtime.md) documents the Basis reference host.

### D.1 Roles

| Role | Responsibility |
|------|----------------|
| **Connector author** | Writes `providers/github/connector.yaml` (Appendix C). |
| **Host operator** | Loads bundles into a catalog, configures platform allowlists. |
| **End user** | Creates a **connection** (OAuth or PAT) in a workspace. |
| **Consumer** | UI, batch job, or agent that calls **primitives**. |

### D.2 Minimal manifest concepts (GitHub `issues`)

From Appendix C, the `issues` entity means: “repository issues for a given `owner` / `repo`”.

- **Static `fields`** — DISCOVER can return these without calling GitHub.  
- **`rest.operations.list`** — `GET /repos/{{config.owner}}/{{config.repo}}/issues` → **LIST** primitive.  
- **`create` / `update`** — **MUTATE** primitives; the body `{"patch": "{{patch}}"}` uses the change set as the entire top-level body (Section 9.4).

Nothing in the YAML contains a token. Auth is declared under `auth` (Section 8). Path values are URL-encoded before the request is sent (Section 9.2).

### D.3 User creates a connection

The host stores something like:

```json
{
  "service": "github",
  "connection_name": "default",
  "auth_type": "api_key",
  "credentials": { "personal_access_token": "…" },
  "connection_config": { "owner": "acme-corp", "repo": "api" }
}
```

`owner` / `repo` fill `{{config.owner}}` and `{{config.repo}}` in paths. When `connection_config` defines them, they are **immutable** for that connection; `action_params` may supply them only when absent (Section 9.1).

### D.4 CHECK (optional but typical)

Runtime: **CHECK** on `service=github`, `connection_name=default`.

Host calls auth `check.path` (`GET /user`) and returns profile fields (`login`, etc.). Failure means fix credentials before LIST.

### D.5 LIST issues (runtime inputs)

| Input | Value |
|-------|--------|
| `service` | `github` |
| `action_id` | `issues` |
| Primitive | LIST (host may expose as `primitive: list`) |
| `action_params` | `{ "owner": "acme-corp", "repo": "api" }` if not in `connection_config` |
| `limit` | optional cap on **records returned by this call** |

**Output (conceptual):** `{ "records": [ … ], "next_cursor_value": "…", "has_more": false }` — record shape matches GitHub JSON (and static `fields` where applicable).

The host may fetch several GitHub pages to satisfy `limit`; `next_cursor_value` is the incremental watermark for a later sync, not a page cursor (Section 10.4).

### D.6 MUTATE create (runtime inputs)

| Input | Value |
|-------|--------|
| Primitive | MUTATE |
| `operation` | `create` |
| `changes` | `{ "title": "Bug from agent", "body": "…" }` |
| `action_params` | scope as above |

`external_id` is omitted for `create`. For `update`, pass `external_id` (issue number) and `operation: update`.

### D.7 Agent exposure (Basis reference host, informative)

Basis exposes a **generic** MCP tool plus **expanded** tools derived from each manifest `actions[]` entry (same runtime; no duplicate YAML operations):

| Surface | Name pattern | Notes |
|---------|--------------|--------|
| Generic | `invoke_connector_primitive` | Pass `service`, `action_id`, `primitive`, … |
| Expanded | `connector_{service}__{action_id}__{suffix}` | `suffix` = `list`, `discover`, `invoke`, or `mutate_{create\|update\|upsert\|delete}` |

`tools/list` is workspace-scoped: provider allowlist and `action_policy.entities` omit tools whose primitive is `disabled` (e.g. `github:issues.list`).

Generic example:

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

Expanded equivalent:

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

HTTP equivalent: `POST /api/v1/workspaces/{workspace_id}/connectors/connections/github/default/invoke-primitive` with the same fields in the JSON body.

### D.8 Ledger path (same manifest, different host binding)

A **sync** job may call the **same** LIST operation internally, then map rows into an internal evidence ledger. That mapping table is **host data**, not part of `connector.yaml`. BOCP does not define mapping schema; see host data models.

### D.9 SQL provider sketch (`postgres`)

Entity `table_records` uses `sql.operations`:

- **DISCOVER** — `discover` with `sql_inspector` (columns from live DB).  
- **LIST** — `list` with runtime `external_table: "customers"`.  
- **MUTATE** — `create` / `update` with table scope + primary key at runtime.

Same primitive vocabulary; only the executor block differs from REST.

### D.10 Checklist for new provider authors

1. Choose `service` id and create `providers/{service}.yaml` with `version: "2.0"`.  
2. Declare at least one `auth` entry with `check` where possible. `api_key` **MUST** state its header or query placement explicitly.  
3. Add `actions[]` with `kind: entity` or `procedure`. Every entity **MUST** include `list`; put **all** wire operations under `rest.operations` or `sql.operations`.  
4. Use only the closed operation keys; a procedure uses exactly `invoke`.  
5. Document required `action_params` / `connection_config` keys in `description`, and remember connection values cannot be overridden per call.  
6. Add `x-` fields only for extensions; any other undeclared field fails validation.  
7. Validate against `manifest_schema.py` and test CHECK + LIST in a host runtime.
