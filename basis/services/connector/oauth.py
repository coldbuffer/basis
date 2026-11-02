"""OAuth authorize / exchange and workspace OAuth config use cases."""

from __future__ import annotations

import uuid
from typing import Any

from basis.services.connector import authz
from basis.services.kernel import WorkspaceCoreContext
from basis.services.connector.vault.connection_scope import SCOPE_END_USER
from basis.services.connector.vault.connector_oauth_state import (
    pack_connector_oauth_state,
    unpack_connector_oauth_state,
)
from basis.services.connector import get_connector_catalog
from basis.services.errors import AdminError


def build_embed_authorize_url(
    ctx: WorkspaceCoreContext,
    *,
    service: str,
    subject_id: str,
    redirect_uri: str | None,
    connection_config: dict[str, Any],
    code_challenge: str | None,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    state = pack_connector_oauth_state(service, subject_id.strip())
    runtime = ctx.knowledge.connector_runtime()
    try:
        url = runtime.vault.build_oauth2_authorize_url(
            ctx.workspace.id,
            service,
            state=state,
            redirect_uri=redirect_uri,
            connection_config=connection_config,
            code_challenge=code_challenge,
        )
    except Exception as exc:
        raise AdminError(422, "oauth_authorize_url_failed", str(exc)) from exc
    return {"authorize_url": url, "state": state}


def exchange_oauth_code(
    ctx: WorkspaceCoreContext,
    *,
    service: str,
    code: str,
    redirect_uri: str | None,
    code_verifier: str | None,
    state: str | None,
    connection_scope: str,
    subject_id: str | None,
    connection_config: dict[str, Any],
    http_client: Any = None,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    scope = connection_scope
    resolved_subject = subject_id
    if state and not resolved_subject:
        try:
            parsed = unpack_connector_oauth_state(state)
            if parsed["service"] != service:
                raise AdminError(422, "oauth_state_mismatch", "state service mismatch")
            resolved_subject = parsed["subject_id"]
            scope = SCOPE_END_USER
        except ValueError as exc:
            raise AdminError(422, "oauth_state_invalid", str(exc)) from exc
    if scope == SCOPE_END_USER and not (resolved_subject or "").strip():
        raise AdminError(422, "subject_id_required", "end_user OAuth requires subject_id")
    runtime = ctx.knowledge.connector_runtime()
    try:
        stored = runtime.vault.exchange_oauth2_code(
            ctx.workspace.id,
            service,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            connection_scope=scope,
            subject_id=resolved_subject,
            connection_config=connection_config,
            http_client=http_client,
        )
    except Exception as exc:
        raise AdminError(422, "oauth_exchange_failed", str(exc)) from exc
    return {"connection": stored.to_public_dict()}


def get_oauth_config_public(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    if not get_connector_catalog().get(service):
        raise AdminError(404, "connector_not_found", f"未知的连接器服务: {service}")
    runtime = ctx.knowledge.connector_runtime()
    public = runtime.vault.get_oauth_config_public(ctx.workspace.id, service)
    if not public:
        raise AdminError(404, "oauth_config_not_found", f"OAuth2 not configured for {service}")
    return {"oauth_config": public}


def upsert_oauth_config(
    ctx: WorkspaceCoreContext,
    *,
    service: str,
    client_id: str,
    client_secret: str | None,
    redirect_uri: str | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    if not get_connector_catalog().get(service):
        raise AdminError(404, "connector_not_found", f"未知的连接器服务: {service}")
    runtime = ctx.knowledge.connector_runtime()
    existing = runtime.vault.get_oauth_config(ctx.workspace.id, service)
    secret = (client_secret or "").strip()
    if not secret:
        prior = str((existing or {}).get("client_secret") or "").strip()
        if prior:
            secret = prior
        else:
            raise AdminError(
                422,
                "oauth_client_secret_required",
                "OAuth2 client_secret is required when no secret is stored yet",
            )
    saved = runtime.vault.upsert_oauth_config(
        ctx.workspace.id,
        service,
        client_id=client_id,
        client_secret=secret,
        redirect_uri=redirect_uri,
        extra=extra,
    )
    return {"oauth_config": saved}


def build_workspace_authorize_url(
    ctx: WorkspaceCoreContext,
    *,
    service: str,
    state: str | None,
    redirect_uri: str | None,
    connection_config: dict[str, Any],
    code_challenge: str | None,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    runtime = ctx.knowledge.connector_runtime()
    resolved_state = state or f"bocp_{uuid.uuid4().hex[:16]}"
    try:
        url = runtime.vault.build_oauth2_authorize_url(
            ctx.workspace.id,
            service,
            state=resolved_state,
            redirect_uri=redirect_uri,
            connection_config=connection_config,
            code_challenge=code_challenge,
        )
        return {"authorize_url": url, "state": resolved_state}
    except Exception as exc:
        raise AdminError(422, "oauth_authorize_url_failed", str(exc)) from exc


def exchange_workspace_oauth_code(
    ctx: WorkspaceCoreContext,
    *,
    service: str,
    code: str,
    redirect_uri: str | None,
    code_verifier: str | None,
    connection_scope: str,
    subject_id: str | None,
    connection_config: dict[str, Any],
    http_client: Any = None,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    runtime = ctx.knowledge.connector_runtime()
    try:
        stored = runtime.vault.exchange_oauth2_code(
            ctx.workspace.id,
            service,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            connection_scope=connection_scope,
            subject_id=subject_id,
            connection_config=connection_config,
            http_client=http_client,
        )
        return {"connection": stored.to_public_dict()}
    except Exception as exc:
        raise AdminError(422, "oauth_exchange_failed", str(exc)) from exc
