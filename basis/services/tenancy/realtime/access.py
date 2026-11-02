"""Revoke realtime graph subscriptions when workspace membership changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request


def revoke_workspace_member_realtime(request: Request, workspace_id: str, user_id: str) -> None:
    """Close open graph-update sockets for a user on a workspace."""
    request.app.state.ws_hub.try_disconnect_user_from_workspace(workspace_id, user_id)


def revoke_user_realtime(request: Request, user_id: str) -> None:
    """Close all graph-update sockets for a user (e.g. account deactivation)."""
    request.app.state.ws_hub.try_disconnect_user(user_id)
