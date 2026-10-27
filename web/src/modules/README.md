# Feature modules (`src/modules/`)

Each folder is one **menu / URL capability** (flat peers — no `kb/` or `platform/` parent).

## Layout (required)

| Directory | Required | Role |
| --- | --- | --- |
| `index.tsx` | **yes** (module root) | Route entry (`Kb*Page`, `*Page`); lazy-load `@/modules/<segment>/index.js` |
| `pages/` | **yes** | Glue (`panel.tsx`, `host.tsx`), main `screen.tsx`, extra route screens |
| `i18n/` | **yes** | `en.ts` + `zh.ts` + `index.ts` barrel (see [i18n-convention.md](./i18n-convention.md)) |
| `components/` | **yes** | Feature UI pieces; `index.ts` may re-export or stay empty |
| `hooks/` | no | `use-*.ts(x)` when the module has local hooks |
| `lib/` | no | Non-UI helpers, API adapters, pure TS |

**Imports**

- Route lazy targets: `@/modules/<segment>/index.js`
- UI strings: edit `i18n/en.ts` and `i18n/zh.ts`; run `refresh-module-i18n-index.mjs` after new modules
- Bridges (legacy): `screen-copy.ts` until callers use `messagesForLocale`
- UI: `@/modules/<segment>/components/…`
- Prefer **relative** imports inside a module (`../lib/…`, `../i18n/…`).

**Rules**

- Only code for **this** capability; no `_shared` / `_shell` under `modules/`.
- Do **not** import UI from another module — use `components/app/shared/workspace/*` or `components/app/shared/*`.
- **`connectors` vs `integration`:** keep separate `lib/` and `components/` even when BOCP forms look alike (playground is not a shared UI layer on top of the connectors console). Backend packages: `domain/connector` + `application/connectors` (UI segment `integration` is not the Python module name).
- Put **this segment’s** screens/panels under `components/`.
- Cross-segment `components/` imports are **forbidden** (CI: `scripts/audit/audit-web-module-cross-ui.py`). Use `components/app/shared/workspace/*` or keep UI in the owning module (e.g. `data-quality/components/`).
- May import `lib/workspace`, `lib/openapi`, `lib/errors`, `app/shared/workspace/*`.
- Other modules’ `lib/` (e.g. `@/modules/graph/lib/graph-url-state.js`) for shared URL helpers — not UI.

**Routing:** URLs in [`routes/index.tsx`](../routes/index.tsx); code-splitting in [`routes/lazy-pages.ts`](../routes/lazy-pages.ts).
