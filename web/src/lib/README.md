# Shared `src/lib/`

Cross-cutting client code for the Basis web app. Feature-specific code: [`modules/<segment>/lib/`](../modules/README.md).

## Layout

| Directory | Role |
| --- | --- |
| **`openapi/`** | Generated transport, `client.ts`, `api-v1-path`, `basis-api-url`, `response`, `spec-url` |
| **`session/`** | `basis-session`, session client/fetch, `auth-token`, `auth-site-url`, legacy `api.ts` login helpers |
| **`workspace/`** | Workspace catalog/capabilities, HTTP/WS, graph store, `request-id`, `realtime-ws-origin` |
| **`nav/`** | `nav-config`, `workspace-nav-label` |
| **`runtime/`** | `app-runtime`, `basis-runtime` |
| **`shell/`** | `theme`, `use-settings-access`, `desktop-bridge` |
| **`marketing/`** | Product site nav, `docs-slug`, `public-icon-map` |
| **`errors/`** | `api-error`, `api-error-message`, `use-api-error-message` |
| **`admin/`** | Admin-only helpers (`csv`, `download-text-blob`, `use-platform-admin-crumbs`) |
| **`ui-classes/`** | Tailwind class bundles (graph, ontology, console, …) |
| **`utils.ts`** | Shared `cn` and small helpers (wide import surface — keep at root) |

## Migrated to `modules/*/lib/`

URL state, segment helpers, docs loaders, alerts, connectors, graph diff/temporal, etc. — see git history / prior commits; do not re-add flat files at `lib/` root.

Cross-module URL helpers: `@/modules/<segment>/lib/…`.
