"""Ontology Hub generated SHACL validation against ledger data graph."""

from __future__ import annotations

import logging
from typing import Any

from basis.domain.knowledge.conflict.scan_context import ConflictScanContext
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.ontology.shacl.shacl_generate import generated_shacl_for_uri

logger = logging.getLogger(__name__)


def hub_shacl_turtle_for_scan(
    knowledge: KnowledgeStore,
    workspace_id: str,
    scan_ctx: ConflictScanContext,
) -> tuple[str, str | None]:
    """Return (shacl_turtle, ontology_uri) from Hub, or ("", None) if unavailable."""
    registry = scan_ctx.ontology_registry or {}
    if not registry or scan_ctx.graph_session is None:
        return "", None
    uri = scan_ctx.ontology_uri or resolve_governance_ontology_uri(
        knowledge, workspace_id, registry
    )
    if not uri:
        return "", None
    from basis.domain.knowledge.services.workspace_shacl import saved_shacl_turtle_for_ontology

    saved = saved_shacl_turtle_for_ontology(knowledge, workspace_id, uri)
    if saved:
        return saved, uri
    try:
        shacl_turtle, _ = generated_shacl_for_uri(
            scan_ctx.graph_session, registry, uri
        )
    except Exception as exc:
        logger.debug("Hub SHACL generation skipped for %s: %s", uri, exc)
        return "", None
    return shacl_turtle, uri


def resolve_governance_ontology_uri(
    knowledge: KnowledgeStore,
    workspace_id: str,
    registry: dict[str, Any],
) -> str | None:
    config = knowledge.get_governance_config(workspace_id)
    if config.governance_ontology_uri:
        return config.governance_ontology_uri.strip()
    for key in sorted(registry.keys()):
        if str(key).strip():
            return str(key).strip()
    return None
