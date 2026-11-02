"""API tokens scoped to one workspace (`workspace_id`)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_workspace_for_admin, get_store

router = APIRouter(tags=["workspaces"])


class CreateWorkspaceApiTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scope: str = "read"
    expires_at: str | None = None
    allowed_operations: list[str] | None = Field(
        default=None,
        description="Deprecated: sets both MCP and OpenAPI grants when the split fields are omitted.",
    )
    mcp_allowed_operations: list[str] | None = Field(
        default=None,
        description="MCP tool names this token may call; omit for unrestricted MCP.",
    )
    http_allowed_operations: list[str] | None = Field(
        default=None,
        description="Workspace REST route grant ids; omit for unrestricted OpenAPI.",
    )


def _tokens_for_workspace(store: AdminStore, user: User, workspace_id: str) -> list:
    return [t for t in store.list_api_tokens(user) if workspace_id in t.workspace_ids]


@router.get("/{workspace_id}/tokens")
async def list_tokens(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List workspace API tokens. Manage workspace API tokens (session + workspace admin only). Requires session JWT (`sessionAuth`).
    """
    get_workspace_for_admin(request, user, workspace_id, store)
    tokens = _tokens_for_workspace(store, user, workspace_id)
    return {"tokens": [t.public() for t in tokens]}


@router.post("/{workspace_id}/tokens")
async def create_token(
    workspace_id: str,
    body: CreateWorkspaceApiTokenRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Create workspace API token. Manage workspace API tokens (session + workspace admin only). Requires session JWT (`sessionAuth`).
    """
    get_workspace_for_admin(request, user, workspace_id, store)
    record, plaintext = store.create_api_token(
        user,
        name=body.name,
        scope=body.scope,
        workspace_ids=[workspace_id],
        expires_at=body.expires_at,
        allowed_operations=body.allowed_operations,
        mcp_allowed_operations=body.mcp_allowed_operations,
        http_allowed_operations=body.http_allowed_operations,
    )
    return {"token": record.public(), "secret": plaintext}


@router.delete("/{workspace_id}/tokens/{token_id}")
async def delete_token(
    workspace_id: str,
    token_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, str]:
    """
Delete Token. Manage workspace API tokens (session + workspace admin only). Requires session JWT (`sessionAuth`).
    """
    get_workspace_for_admin(request, user, workspace_id, store)
    matches = [t for t in _tokens_for_workspace(store, user, workspace_id) if t.id == token_id]
    if not matches:
        raise AdminError(404, "not_found", "令牌不存在或不属于此工作区")
    store.delete_api_token(user, token_id)
    return {"status": "deleted"}
