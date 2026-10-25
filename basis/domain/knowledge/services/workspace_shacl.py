"""Workspace-persisted SHACL shapes used by conflict scans and SHACL studio."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


def saved_shacl_turtle_for_ontology(
    knowledge: KnowledgeStore,
    workspace_id: str,
    ontology_uri: str,
) -> str | None:
    """Return saved Turtle when it applies to ``ontology_uri``."""
    uri = str(ontology_uri or "").strip()
    if not uri:
        return None
    config = knowledge.get_governance_config(workspace_id)
    bound = (config.governance_ontology_uri or "").strip()
    if bound != uri:
        return None
    raw = config.governance_shacl_turtle
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip()
