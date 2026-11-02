"""Workspace-scoped forward-chaining rule library (F-RUL-01)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

import asyncio

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_workspace_for_editor, get_workspace_for_viewer, get_knowledge_store, get_store
from basis.http.core_context import build_workspace_core_context
from basis.http.operation_http import http_response_from_payload
from basis.services.graph.operations import op_get_rule, op_list_rules
from basis.services.knowledge.store import KnowledgeStore

router = APIRouter(tags=["workspaces"])


class CreateReasoningRuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=16000)
    enabled: bool = True


class UpdateReasoningRuleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=16000)
    enabled: bool | None = None


@router.get("/{workspace_id}/rules")
async def list_reasoning_rules(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Reasoning Rules. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_list_rules, ctx, {"limit": limit})


@router.get("/{workspace_id}/rules/{rule_id}")
async def get_reasoning_rule(
    workspace_id: str,
    rule_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Get Reasoning Rule. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(op_get_rule, ctx, {"rule_id": rule_id})
    return http_response_from_payload(payload)


@router.post("/{workspace_id}/rules")
async def create_reasoning_rule(
    workspace_id: str,
    body: CreateReasoningRuleRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Create Reasoning Rule. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    rule = knowledge.create_reasoning_rule(
        workspace_id,
        name=body.name.strip(),
        body=body.body.strip(),
        actor_id=user.id,
        enabled=body.enabled,
    )
    return {"rule": rule}


@router.patch("/{workspace_id}/rules/{rule_id}")
async def update_reasoning_rule(
    workspace_id: str,
    rule_id: str,
    body: UpdateReasoningRuleRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Update Reasoning Rule. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    rule = knowledge.update_reasoning_rule(
        workspace_id,
        rule_id,
        name=body.name.strip() if body.name is not None else None,
        body=body.body.strip() if body.body is not None else None,
        enabled=body.enabled,
    )
    return {"rule": rule}


@router.delete("/{workspace_id}/rules/{rule_id}")
async def delete_reasoning_rule(
    workspace_id: str,
    rule_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Delete Reasoning Rule. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    knowledge.delete_reasoning_rule(workspace_id, rule_id)
    return {"ok": True}
