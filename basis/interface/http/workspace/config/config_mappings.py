"""Workspace ontology mapping ledger routes."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from basis.application.knowledge.operations import (
    op_assign_entity_types,
    op_clear_entity_types,
    op_list_mappings,
    op_propose_mapping,
    op_update_mapping_status,
)
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.shared.deps import (
    get_current_user,
    get_store,
    get_workspace_for_editor,
)

router = APIRouter(tags=["workspaces"])


class AssignEntityTypesRequest(BaseModel):
    assignments: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    replace_existing: bool = True


class ClearEntityTypesRequest(BaseModel):
    subject_ids: list[str] = Field(min_length=1, max_length=200)


class CreateMappingRequest(BaseModel):
    signature: str | None = Field(default=None, max_length=512)
    subject_id: str | None = Field(default=None, max_length=2048)
    target_uri: str | None = Field(default=None, max_length=2048)
    target_kind: Literal["class", "property", "none"] = "property"
    direction: Literal["forward", "reverse", "n/a"] = "forward"
    status: Literal["proposed", "confirmed"] = "proposed"
    why: str | None = Field(default=None, max_length=2000)


class UpdateMappingStatusRequest(BaseModel):
    status: Literal["confirmed", "rejected", "superseded"]
    why: str | None = Field(default=None, max_length=2000)


@router.get("/{workspace_id}/mappings")
async def list_mappings(
    workspace_id: str,
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List Mappings. Statement-to-entity mapping proposals and status. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    args: dict[str, Any] = {"limit": limit}
    if status:
        args["status"] = status
    return await asyncio.to_thread(op_list_mappings, ctx, args)


@router.post("/{workspace_id}/entity-types/assign")
async def assign_entity_types(
    workspace_id: str,
    body: AssignEntityTypesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Assign rdf:type to subjects (ledger entity or graph node id). Editor only.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_assign_entity_types, ctx, body.model_dump())


@router.post("/{workspace_id}/entity-types/clear")
async def clear_entity_types(
    workspace_id: str,
    body: ClearEntityTypesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Clear rdf:type typed_facts for subjects. Editor only.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_clear_entity_types, ctx, body.model_dump())


@router.post("/{workspace_id}/mappings")
async def create_mapping(
    workspace_id: str,
    body: CreateMappingRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Create Mapping. Statement-to-entity mapping proposals and status. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    minimum = "editor" if body.status == "confirmed" else "viewer"
    store.get_workspace_for(user, workspace_id, minimum)
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_propose_mapping, ctx, body.model_dump(exclude_none=True))


@router.post("/{workspace_id}/mappings/{mapping_id}/status")
async def update_mapping_status(
    workspace_id: str,
    mapping_id: str,
    request: Request,
    body: UpdateMappingStatusRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Update Mapping Status. Statement-to-entity mapping proposals and status. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    ctx = build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=True,
    )
    args = {"mapping_id": mapping_id, **body.model_dump(exclude_none=True)}
    return await asyncio.to_thread(op_update_mapping_status, ctx, args)
