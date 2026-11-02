# `basis.domain.ontology`

Business-semantics **model layer** for a workspace (`workspace_id`): Ontology Hub (registry, drafts, proposals), SHACL, browse/preview, RDF I/O, and shared RDF parse helpers (`io/`).

Graph **projection** and interactive reads live in `basis.domain.graph` (`projection/`, `session/`, `reads/`, …). Canonical facts remain in `basis.domain.knowledge`.

## Subpackages

| Path | Responsibility |
| --- | --- |
| `hub/` | Registry, `draft_apply` (editor `DraftDiff` → graph on publish), governance lifecycle |
| `persistence/` | Canonical SQL (`sql_alignments`, `sql_mappings`, `sql_reasoning_rules`) and Hub sidecar/state stores (`hub_persistence`, `draft_store`, `proposal_store`, `version_store`) |
| `shacl/` | Generate, validate, read SHACL |
| `browse/` | Graph scope, health, SKOS-oriented reads, preview |
| `io/` | RDF parse (`rdf_parse`, `rdf_io`) + admin error mapping for ontology HTTP |
| `vocabulary/` | SKOS schemes, concepts, import |
| `mappings/` | Statement surface → ontology URI mappings (`MappingsAccess`, `service`, `entity_type`) |
| `reasoning_rules/` | Forward-reasoning rule rows (`ReasoningRulesAccess`) |
| `legacy_graph_create.py` | Legacy `POST …/ontology` graph-node fallback |

## Imports

```python
from basis.domain.ontology.hub.catalog import list_registry
from basis.domain.ontology.hub.scoped_state import OntologyHubState
from basis.domain.ontology.io.rdf_parse import safe_parse_rdf
```
