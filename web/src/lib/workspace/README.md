# Workspace client (`lib/workspace/`)

Everything scoped to `/workspaces/:id/*` console routes: React frame, HTTP/WS, and graph session client state.

## Frame (providers)

| File | Role |
| --- | --- |
| `context.tsx` | Workspace catalog (`WorkspaceCatalogProvider`, `useWorkspaceCatalog`) |
| `capabilities.tsx` | Feature flags / nav gating (`graph_runtime`, segments, …) |
| `active-id.ts` | Active workspace id (localStorage, setup id, sidebar resolve) |

## HTTP / WebSocket

Typed per-workspace REST helpers: `basisSessionClient().workspace(workspaceId)` in `@/lib/openapi/transport.js` (search/chunks, entities, graph search, MCP info).

| File | Role |
| --- | --- |
| `ws-http.tsx` | `WorkspaceHostProvider`, `workspaceFetch` (session Bearer, same as OpenAPI), path builders |
| `api-path.ts` | `workspaceApiRoot`, `workspaceApiPath` |
| `ws-host.ts` | `buildWorkspaceHttpConfig` |
| `ws-client.ts` / `ws-context.tsx` | Ingest WS client + route shell |
| `ws-api-error.ts` | Workspace JSON error helpers |
| `node-labels.ts`, `format-node-ref.ts` | Label resolve + display |

## Graph canvas (client)

| File | Role |
| --- | --- |
| `graphStore.ts`, `graphTheme.ts`, `edgePairKeys.js` | Sigma scene state + theme tokens |

Graph-only UI/helpers (`graph-surface-primitives`, `registry-store`) live under `modules/graph/lib/`.

Segment-specific helpers: `modules/<segment>/lib/` — see [`lib/README.md`](../README.md).
