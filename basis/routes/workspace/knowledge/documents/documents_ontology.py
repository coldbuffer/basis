"""Legacy graph-session ontology create (``POST /{workspace_id}/ontology``)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    graph_runtime_for,
    get_current_user,
    get_store,
    graph_for,
    save_graph,
)
from basis.services.ontology.hub.scoped_state import OntologyHubState
from basis.services.ontology.hub.registry_write import create_ontology as create_ontology_domain
from basis.services.graph.session.guard import require_graph_session
from basis.services.ontology.legacy_graph_create import LegacyGraphOntologyService
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.routes.workspace.knowledge.documents.documents_models import CreateOntologyRequest

router = APIRouter(tags=["workspaces"])
_ontology = LegacyGraphOntologyService()


@router.post("/{workspace_id}/ontology")
async def create_ontology(
    workspace_id: str,
    body: CreateOntologyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Create Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    store.get_workspace_for(user, workspace_id, "admin")
    if graph_runtime_available():
        runtime = graph_runtime_for(request, workspace_id)
        session = require_graph_session(runtime)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await asyncio.to_thread(
                create_ontology_domain,
                session,
                registry,
                namespace=body.namespace,
                name=body.name,
                description=body.description,
                mode="scratch",
            )
    else:
        result = _ontology.create(
            graph_for(request, workspace_id),
            namespace=body.namespace,
            name=body.name,
            description=body.description,
        )
    save_graph(request, workspace_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.ontology_create",
        extra={"uri": result["uri"], "name": body.name, "namespace": body.namespace},
    )
    return result
