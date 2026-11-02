# `basis.domain.graph`

Graph **projection** (`projection/`) and **interactive session** subpackages for the workspace graph UI (`web/src/modules/graph/`, `web/src/lib/workspace/`). Mutations still flow through Review / ledger APIs — not a second write path.

**Architecture docs:** [graph-workspace-integration.md](../../../docs/architecture/graph-workspace-integration.md), [graph-workspace-backend.md](../../../docs/architecture/graph-workspace-backend.md), [package-layout.md](../../../docs/architecture/package-layout.md) (import rules).

## Subpackages

| Path | Responsibility |
| --- | --- |
| `projection/` | Ledger → ContextGraph projection, persistence, lifecycle |
| `session/` | `GraphSessionRegistry`, auth guard, probe, `BasisGraphSession` |
| `reads/` | Projection reads, diff, staging payloads, import/export, semantic neighborhood |
| `governance/` | Decisions, enrich, provenance, governance trip side effects |
| `temporal/` | Temporal bounds and snapshots |
| `sparql/` | Read-only SPARQL over projection |
| `reasoning/` | Forward reasoning run + helpers (`forward.py`) |

Ontology Hub, SHACL, and RDF model I/O: **`basis/domain/ontology/`** (see [ontology README](../ontology/README.md)).

## Imports

Use **subpackage modules**, for example:

```python
from basis.domain.graph.session.registry import GraphSessionRegistry
from basis.domain.graph.reads.read import get_node
from basis.domain.ontology.hub.catalog import list_ontologies
```

Do not reintroduce flat modules at the `graph/` package root — CI runs `scripts/audit/audit-graph-shim-imports.py` to block new compatibility shims in `basis/` and `tests/`.

Private symbols (`_parse_fact`, registry helpers, etc.) must be imported from the subpackage module that defines them.
