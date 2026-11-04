"""Workspace SQL catalog sources: schema snapshots, not row copies."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from basis.http.deps import (
    get_current_user,
    get_knowledge_store,
    get_store,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    graph_runtime_for,
    save_graph,
)
from basis.services.graph.session.guard import require_graph_session
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.services.knowledge.store import KnowledgeStore
from basis.services.ontology.hub.scoped_state import OntologyHubState
from basis.services.sql_catalog.access import SqlCatalogAccess
from basis.services.sql_catalog.ontology_map import apply_catalog_ontology
from basis.services.tenancy.admin.store import AdminStore, User

router = APIRouter(tags=["workspaces"])


class TestSqlCatalogConnectionRequest(BaseModel):
    connection_uri: str = Field(min_length=1)


class UpsertSqlCatalogSourceRequest(BaseModel):
    display_name: str = Field(min_length=1)
    connection_uri: str = Field(min_length=1)
    table_allow_regex: str | None = None
    table_deny_regex: str | None = None
    schemas: list[str] | None = None


def _access(knowledge: KnowledgeStore) -> SqlCatalogAccess:
    return SqlCatalogAccess(knowledge)


@router.get("/{workspace_id}/sql-catalog/sources")
async def list_sql_catalog_sources(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """List SQL catalog sources. Each source points at a database whose schema can be snapshotted. Connection secrets are redacted. Requires workspace read access."""
    get_workspace_for_viewer(request, user, workspace_id, store)
    return {"sources": _access(knowledge).list_sources(workspace_id)}


@router.post("/{workspace_id}/sql-catalog/connection-test")
async def test_sql_catalog_connection(
    workspace_id: str,
    request: Request,
    body: TestSqlCatalogConnectionRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Open the database and run a connectivity check. Does not store the connection or copy table rows. Requires workspace write access."""
    get_workspace_for_editor(request, user, workspace_id, store)
    _access(knowledge).test_connection(body.connection_uri)
    return {"ok": True}


@router.put("/{workspace_id}/sql-catalog/sources/{source_id}")
async def upsert_sql_catalog_source(
    workspace_id: str,
    source_id: str,
    request: Request,
    body: UpsertSqlCatalogSourceRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Create or replace a SQL catalog source. Opens the database and runs a connectivity check before storing the connection string. A failed check does not save the source. Does not copy table rows. Requires workspace write access."""
    get_workspace_for_editor(request, user, workspace_id, store)
    source = _access(knowledge).upsert_source(
        workspace_id,
        source_id,
        display_name=body.display_name,
        connection_uri=body.connection_uri,
        table_allow_regex=body.table_allow_regex,
        table_deny_regex=body.table_deny_regex,
        schemas=body.schemas,
    )
    return {"source": source}


@router.delete("/{workspace_id}/sql-catalog/sources/{source_id}")
async def delete_sql_catalog_source(
    workspace_id: str,
    source_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Delete a SQL catalog source and its stored schema snapshot. Requires workspace write access."""
    get_workspace_for_editor(request, user, workspace_id, store)
    _access(knowledge).delete_source(workspace_id, source_id)
    return {"deleted": True}


@router.post("/{workspace_id}/sql-catalog/sources/{source_id}/snapshot")
async def snapshot_sql_catalog_source(
    workspace_id: str,
    source_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Read tables, columns, views, keys, and recent query text from the source database and store that schema snapshot. Does not copy source rows. Requires workspace write access."""
    get_workspace_for_editor(request, user, workspace_id, store)
    return {"snapshot": _access(knowledge).snapshot_source(workspace_id, source_id)}


@router.get("/{workspace_id}/sql-catalog/sources/{source_id}/snapshot")
async def get_sql_catalog_snapshot(
    workspace_id: str,
    source_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Return the latest stored schema snapshot for a SQL catalog source. Requires workspace read access."""
    get_workspace_for_viewer(request, user, workspace_id, store)
    return {"snapshot": _access(knowledge).get_snapshot(workspace_id, source_id)}


@router.post("/{workspace_id}/sql-catalog/sources/{source_id}/ontology")
async def apply_sql_catalog_ontology(
    workspace_id: str,
    source_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Write the latest schema snapshot into the workspace ontology as classes, datatype properties, and foreign-key object properties. Does not copy source rows. Requires workspace write access."""
    get_workspace_for_editor(request, user, workspace_id, store)
    prepared = _access(knowledge).snapshot_for_ontology(workspace_id, source_id)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    with OntologyHubState(request, workspace_id):
        registry = request.app.state.ontology_registries[workspace_id]
        result = await asyncio.to_thread(
            apply_catalog_ontology,
            session,
            registry,
            source_id=prepared["source_id"],
            display_name=prepared["display_name"],
            catalog=prepared["catalog"],
        )
    save_graph(request, workspace_id, sync_ledger=False)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.sql_catalog_ontology",
        extra={"uri": result["uri"], "name": result["name"], "source_id": source_id},
    )
    return result
