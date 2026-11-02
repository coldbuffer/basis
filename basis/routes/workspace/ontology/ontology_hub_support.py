"""Shared helpers for workspace ontology hub HTTP route modules."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import graph_runtime_for
from basis.services.graph.session.guard import require_graph_session
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.services.graph.governance.decision import emit_governance_tripped_for_workspace
from basis.services.knowledge.store import KnowledgeStore

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def ontology_session(request: Request, workspace_id: str):
    runtime = graph_runtime_for(request, workspace_id)
    return require_graph_session(runtime)


def min_role(method: str) -> str:
    return "editor" if method in WRITE_METHODS else "viewer"


def governance_alert_from_proposal_result(
    request: Request,
    workspace_id: str,
    knowledge: KnowledgeStore,
    proposal_id: str,
    result: Any,
    *,
    actor_id: str | None = None,
) -> None:
    if hasattr(result, "model_dump"):
        data: Any = result.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        return
    shacl = data.get("shacl_validation")
    if isinstance(shacl, dict) and shacl.get("conforms") is False:
        emit_governance_tripped_for_workspace(
            request,
            workspace_id,
            knowledge,
            message=f"SHACL gate failed for proposal {proposal_id}",
            detail={
                "proposal_id": proposal_id,
                "shacl_validation": shacl,
            },
            actor_id=actor_id,
        )


def audit_ontology_graph_write(
    store: AdminStore,
    user: User,
    workspace_id: str,
    action: str,
    result: Any,
) -> None:
    extra: dict[str, Any] = {}
    if hasattr(result, "model_dump"):
        data: Any = result.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        data = {}
    for key in ("uri", "ontology_uri", "name", "namespace", "format", "source"):
        value = data.get(key)
        if value:
            extra[key] = value
    audit_graph(store, user, workspace_id, action, extra=extra or None)
