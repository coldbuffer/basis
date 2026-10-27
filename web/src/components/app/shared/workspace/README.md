# Workspace frame (`app/shared/workspace/`)

Per-workspace **console chrome** (switcher, shells, unavailable states) and small shared ledger primitives.

| Path | Import |
| --- | --- |
| `frame/` | `@/components/app/shared/workspace/frame/` |
| `entity-ref-line.tsx` | `@/components/app/shared/workspace/entity-ref-line.js` |
| `graph-rebuild-button.tsx` | `@/components/app/shared/workspace/graph-rebuild-button.js` |
| `ledger-entity-browser.tsx` | `@/components/app/shared/workspace/ledger-entity-browser.js` (`LedgerEntityHit`) |
| `derived-fact-card.tsx` | `@/components/app/shared/workspace/derived-fact-card.js` |
| `graph-audit-event-links.tsx` | `@/components/app/shared/workspace/graph-audit-event-links.js` |
| `entity-merge-property-diff.tsx` | `@/components/app/shared/workspace/entity-merge-property-diff.js` |
| `processing-options-snapshot.tsx` | `@/components/app/shared/workspace/processing-options-snapshot.js` |
| `import-export/` | `@/components/app/shared/workspace/import-export/import-export-dialog.js` (`ImportExportDialog`) |
| `ontology-workspace-context.tsx` | Workspace id + `ontology/` / `vocabulary/` API path helpers |
| `ontology-shacl-panel.tsx` | SHACL studio shell (data quality + shared entry) |

HTTP/WebSocket: `@/lib/workspace/` (`ws-http`, `ws-host`, `ws-context`). Catalog/capabilities: `@/lib/workspace/`.

Shell roots use the `basis-ws-console` CSS hook (and segment classes like `basis-graph-canvas`) plus `data-workspace-id` for E2E targeting.
