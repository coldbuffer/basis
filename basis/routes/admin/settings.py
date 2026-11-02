from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from basis.services.connector import get_connector_catalog
from basis.services.connector.vault.allowlist import (
    assert_allowed_providers_in_catalog,
    count_platform_enabled,
    is_platform_provider_allowed,
    normalize_allowed_providers,
    unknown_catalog_providers,
)
from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store, require_system_admin
from basis.services.tenancy.identity.settings import invalidate_app_auth_settings

router = APIRouter(tags=["settings"])


class AccessCredentialsPatch(BaseModel):
    class EmailCreds(BaseModel):
        transport: str | None = None
        api_key: str | None = None
        from_: str | None = Field(None, alias="from")
        host: str | None = None
        port: int | None = None
        username: str | None = None
        password: str | None = None

    class OAuthCreds(BaseModel):
        client_id: str | None = None
        client_secret: str | None = None

    email: EmailCreds | None = None
    oauth: dict[str, OAuthCreds] | None = None

    model_config = {"populate_by_name": True}


class AccessSettingsRequest(BaseModel):
    auth_providers: list[str] | None = None
    signup_policy: str | None = None
    public_url: str | None = None
    web_origin: str | None = None
    magic_link_dev_log: bool | None = None
    credentials: AccessCredentialsPatch | None = None


class ConnectorAllowlistSettingsRequest(BaseModel):
    allowed_providers: list[str] | str = "*"


class SettingsRequest(BaseModel):
    open_registration: bool | None = None
    chat_provider: str | None = None
    chat_base_url: str | None = None
    chat_model: str | None = None
    chat_api_key: str | None = None
    embed_provider: str | None = None
    embed_base_url: str | None = None
    embed_model: str | None = None
    embed_api_key: str | None = None


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Get Settings. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    return store.get_settings()


@router.put("")
async def put_settings(
    body: SettingsRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Put Settings. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    return store.update_settings(user, body.model_dump(exclude_unset=True))


def _default_public_url(request: Request) -> str:
    app_settings = request.app.state.settings
    return f"http://{app_settings.host}:{app_settings.port}".rstrip("/")


@router.get("/access")
async def get_access(
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Get Access. Platform system settings (admin). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    return store.get_access_settings(default_public_url=_default_public_url(request))


@router.put("/access")
async def put_access(
    request: Request,
    body: AccessSettingsRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Put Access. Platform system settings (admin). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    payload = body.model_dump(exclude_unset=True, by_alias=True)
    if body.credentials is not None:
        creds = body.credentials.model_dump(exclude_unset=True, by_alias=True)
        payload["credentials"] = creds
    result = store.update_access_settings(
        user,
        payload,
        default_public_url=_default_public_url(request),
    )
    invalidate_app_auth_settings(request)
    return result


@router.get("/connectors")
async def get_connector_allowlist_settings(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Get platform-wide BOCP provider allowlist (workspace policies must stay within this ceiling)."""
    require_system_admin(user)
    allowed = store.get_platform_allowed_providers()
    catalog = get_connector_catalog()
    stats = catalog.summary_stats()
    all_services = catalog.service_ids()
    return {
        "allowed_providers": allowed,
        "stats": stats,
        "enabled_provider_count": count_platform_enabled(allowed, all_services),
        "restrict_mode": normalize_allowed_providers(allowed) != "*",
    }


@router.get("/connectors/catalog/stats")
async def platform_connector_catalog_stats(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Aggregate BOCP catalog counts by category for platform administrators."""
    require_system_admin(user)
    catalog = get_connector_catalog()
    allowed = store.get_platform_allowed_providers()
    return {
        "stats": catalog.summary_stats(),
        "enabled_provider_count": count_platform_enabled(allowed, catalog.service_ids()),
        "category_breakdown": catalog.category_breakdown(platform_allowed=allowed),
    }


@router.get("/connectors/catalog/{service}")
async def get_platform_connector_manifest(
    service: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Return full BOCP manifest JSON for one catalog service (system administrators)."""
    require_system_admin(user)
    catalog = get_connector_catalog()
    manifest = catalog.get(service)
    if not manifest:
        raise AdminError(404, "connector_not_found", f"未知的连接器服务: {service}")
    allowed = store.get_platform_allowed_providers()
    return {
        "service": service,
        "platform_enabled": is_platform_provider_allowed(service, allowed),
        "connector": manifest.model_dump(mode="json", exclude_none=True),
    }


@router.get("/connectors/catalog")
async def list_platform_connector_catalog(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    category: str | None = Query(default=None),
    auth_mode: str | None = Query(default=None),
    has_streams_only: bool = Query(default=False),
    query: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List BOCP catalog entries with platform allowlist flags for system administrators."""
    require_system_admin(user)
    catalog = get_connector_catalog()
    allowed = store.get_platform_allowed_providers()
    manifests = catalog.list_manifests(
        category=category,
        auth_mode=auth_mode,
        has_streams_only=has_streams_only,
        query=query,
    )
    page = manifests[offset : offset + limit]
    return {
        "stats": catalog.summary_stats(),
        "allowed_providers": allowed,
        "enabled_provider_count": count_platform_enabled(allowed, catalog.service_ids()),
        "restrict_mode": normalize_allowed_providers(allowed) != "*",
        "categories": catalog.category_labels(),
        "total_matched": len(manifests),
        "offset": offset,
        "limit": limit,
        "connectors": [
            {
                "service": m.service,
                "display_name": m.display_name,
                "description": m.description,
                "categories": m.categories,
                "auth_modes": [a.auth_mode for a in m.auth],
                "stream_count": len(m.streams),
                "tool_count": len(m.tools),
                "platform_enabled": is_platform_provider_allowed(m.service, allowed),
            }
            for m in page
        ],
    }


@router.post("/connectors/validate")
async def validate_connector_allowlist_settings(
    body: ConnectorAllowlistSettingsRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Validate a platform allowlist against the shipped BOCP catalog."""
    require_system_admin(user)
    allowed = normalize_allowed_providers(body.allowed_providers)
    catalog = get_connector_catalog()
    unknown = unknown_catalog_providers(allowed, catalog.service_ids())
    return {"ok": not unknown, "unknown_providers": unknown}


@router.put("/connectors")
async def put_connector_allowlist_settings(
    body: ConnectorAllowlistSettingsRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Update platform-wide BOCP provider allowlist."""
    require_system_admin(user)
    allowed = normalize_allowed_providers(body.allowed_providers)
    catalog = get_connector_catalog()
    try:
        assert_allowed_providers_in_catalog(allowed, catalog.service_ids())
    except ValueError as exc:
        raise AdminError(400, "connector_unknown_providers", str(exc)) from exc
    allowed, updated_at = store.upsert_platform_allowed_providers(allowed)
    return {"allowed_providers": allowed, "updated_at": updated_at}
