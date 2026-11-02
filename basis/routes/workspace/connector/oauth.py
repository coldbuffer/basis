"""BOCP connector routes — OAuth client config and token exchange."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.services.connector import oauth as oauth_uc
from basis.services.kernel import CoreError
from basis.http.operation_http import http_exception_from_core
from basis.services.tenancy.admin.store import AdminStore, User
from basis.infra.runtime.config import Settings
from basis.infra.e2e_sandbox.playwright_e2e import is_playwright_e2e_data_dir
from basis.infra.e2e_sandbox.playwright_oauth_stub import playwright_e2e_oauth_http_client
from basis.routes.workspace.connector.models import (
    BuildOAuthAuthorizeUrlRequest,
    ExchangeOAuthCodeRequest,
    UpsertOAuthConfigRequest,
)
from basis.http.core_context import build_workspace_core_context
from basis.http.deps import get_current_user, get_store

router = APIRouter(tags=["workspaces"])


@router.get("/{workspace_id}/connectors/oauth-configs/{service}")
async def get_connector_oauth_config(
    workspace_id: str,
    service: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Return OAuth2 app metadata for editors (client_secret is never exposed)."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return oauth_uc.get_oauth_config_public(ctx, service=service)
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.put("/{workspace_id}/connectors/oauth-configs/{service}")
async def upsert_connector_oauth_config(
    workspace_id: str,
    service: str,
    body: UpsertOAuthConfigRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Store encrypted OAuth2 client credentials (`client_id`, `client_secret`) for a connector service."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return oauth_uc.upsert_oauth_config(
            ctx,
            service=service,
            client_id=body.client_id,
            client_secret=body.client_secret,
            redirect_uri=body.redirect_uri,
            extra=body.extra,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/oauth/{service}/authorize-url")
async def build_connector_oauth_authorize_url(
    workspace_id: str,
    service: str,
    body: BuildOAuthAuthorizeUrlRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Build an OAuth2 authorization URL (with optional PKCE S256) for a connector service."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return oauth_uc.build_workspace_authorize_url(
            ctx,
            service=service,
            state=body.state,
            redirect_uri=body.redirect_uri,
            connection_config=body.connection_config,
            code_challenge=body.code_challenge,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/oauth/{service}/exchange")
async def exchange_connector_oauth_code(
    workspace_id: str,
    service: str,
    body: ExchangeOAuthCodeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Exchange an OAuth2 authorization code for tokens and save the encrypted BOCP connection."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        settings: Settings = request.app.state.settings
        http_client = None
        if is_playwright_e2e_data_dir(settings.data_dir):
            http_client = playwright_e2e_oauth_http_client(body.code)
        return oauth_uc.exchange_workspace_oauth_code(
            ctx,
            service=service,
            code=body.code,
            redirect_uri=body.redirect_uri,
            code_verifier=body.code_verifier,
            connection_scope=body.connection_scope,
            subject_id=body.subject_id,
            connection_config=body.connection_config,
            http_client=http_client,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc
