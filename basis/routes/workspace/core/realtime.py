"""Workspace-scoped realtime tickets and graph update WebSocket."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_knowledge_store, get_store, get_workspace_for_viewer

router = APIRouter(tags=["realtime"])

_DEV_WS_ORIGINS = frozenset(
    {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3002",
        "http://localhost:3002",
    }
)


def _allowed_ws_origins(websocket: WebSocket) -> frozenset[str]:
    allowed = set(_DEV_WS_ORIGINS)
    store: AdminStore = websocket.app.state.store
    app_settings = websocket.app.state.settings
    public = f"http://{app_settings.host}:{app_settings.port}".rstrip("/")
    from basis.services.tenancy.identity.settings import load_auth_settings_from_store

    auth = load_auth_settings_from_store(
        store,
        default_public_url=public,
    )
    for candidate in (auth.web_origin, auth.public_url):
        if candidate:
            allowed.add(candidate.rstrip("/"))
    return frozenset(allowed)


def _check_ws_origin(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin is None:
        return
    if origin.rstrip("/") not in _allowed_ws_origins(websocket):
        raise AdminError(403, "forbidden_origin", "来源不被允许")


@router.post("/{workspace_id}/realtime-ticket")
async def create_realtime_ticket(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Create Realtime Ticket. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    ticket, expires_at = request.app.state.realtime_tickets.issue(workspace_id, user.id)
    revision = get_knowledge_store(request).get_projection_state(workspace_id)["revision"]
    return {
        "ticket": ticket,
        "expires_at": expires_at,
        "workspace_id": workspace_id,
        "projection_revision": revision,
    }


@router.websocket("/{workspace_id}/ws/graph-updates")
async def graph_updates_ws(
    websocket: WebSocket,
    workspace_id: str,
    ticket: str,
) -> None:
    app = websocket.app
    try:
        _check_ws_origin(websocket)
        user_id = app.state.realtime_tickets.consume(workspace_id, ticket)
        store: AdminStore = app.state.store
        user = await asyncio.to_thread(store.get_user_by_id, user_id)
        if user is None:
            raise AdminError(401, "unauthorized", "用户无效")
        await asyncio.to_thread(store.get_workspace_for, user, workspace_id, "viewer")
    except AdminError:
        await websocket.close(code=4401)
        return

    hub = app.state.ws_hub
    knowledge = app.state.knowledge_store
    revision = knowledge.get_projection_state(workspace_id)["revision"]

    await hub.connect(workspace_id, websocket, user.id)
    try:
        await websocket.send_json(
            {
                "type": "connected",
                "workspace_id": workspace_id,
                "projection_revision": revision,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(workspace_id, websocket)
