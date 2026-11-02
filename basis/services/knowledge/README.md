# Knowledge domain (ledger)

| Layer | Path | Role |
| --- | --- | --- |
| Façade | `store.py`, `access/*` | Workspace-scoped ledger API |
| SQL persistence | `persistence/sql_<topic>.py` | Canonical DB access (caller holds lock) |
| Connector bridge | `ports/connector.py` | Whitelisted `domain.connector` imports for vault/runtime |
| Services / pipeline | `services/`, `pipeline/` | Orchestration above SQL |

Inside knowledge: import `basis.domain.knowledge.persistence.sql_<topic>`.
Other domains: use `basis.domain.knowledge.sql` for connector vault/sync types only
(`tenancy/admin` workspace purge may import `persistence.sql_delete` directly).
