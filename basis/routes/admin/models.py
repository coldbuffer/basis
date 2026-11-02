from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store, require_system_admin

router = APIRouter(tags=["models"])

ModelKind = Literal["llm", "embed"]


class CreateModelRequest(BaseModel):
    kind: ModelKind
    provider: str = ""
    api_base: str = ""
    model: str = ""
    api_key: str = ""
    display_name: str | None = None
    enabled: bool = True


class UpsertModelEndpointRequest(BaseModel):
    kind: ModelKind
    provider: str = ""
    api_base: str = ""
    api_key: str = ""


class CreateModelsBatchRequest(BaseModel):
    kind: ModelKind
    provider: str = ""
    api_base: str = ""
    models: list[str]
    api_key: str = ""


class PatchModelRequest(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None


@router.get("")
async def list_models(
    kind: ModelKind | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
List Models. LLM model catalog configuration. Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    models = store.list_configured_models(kind)
    return {"models": models}


@router.post("")
async def create_model(
    body: CreateModelRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Create Model. LLM model catalog configuration. Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    entry = store.add_configured_model(
        user,
        body.kind,
        provider=body.provider,
        api_base=body.api_base,
        model=body.model,
        api_key=body.api_key,
        display_name=body.display_name,
        enabled=body.enabled,
    )
    return {"model": entry}


@router.put("/endpoint")
async def upsert_model_endpoint(
    body: UpsertModelEndpointRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Upsert Model Endpoint. Platform LLM/embed API credentials (model id chosen per feature). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    entry = store.upsert_kind_endpoint(
        user,
        body.kind,
        provider=body.provider,
        api_base=body.api_base,
        api_key=body.api_key,
    )
    return {"model": entry}


@router.post("/batch")
async def create_models_batch(
    body: CreateModelsBatchRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Create Models (batch). Add multiple model IDs for one provider endpoint. Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    result = store.add_configured_models_batch(
        user,
        body.kind,
        provider=body.provider,
        api_base=body.api_base,
        models=body.models,
        api_key=body.api_key,
    )
    return result


@router.patch("/{model_id}")
async def patch_model(
    model_id: str,
    body: PatchModelRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Patch Model. LLM model catalog configuration. Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    entry = store.patch_configured_model(
        user,
        model_id,
        enabled=body.enabled,
        api_key=body.api_key,
    )
    return {"model": entry}


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Delete Model. LLM model catalog configuration. Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    store.delete_configured_model(user, model_id)
    return {"ok": True}


# ── Model providers (/model-providers) ──


from basis.services.tenancy.catalog.remote_models import fetch_remote_models
from basis.services.tenancy.catalog.setup_providers import ModelKind, get_provider, infer_provider_id, provider_payload, providers_for_kind

providers_router = APIRouter(tags=["model-providers"])


class ProbeRequest(BaseModel):
    kind: Literal["llm", "embed"] = "llm"
    provider: str = ""
    api_key: str = ""
    api_base: str = ""


@providers_router.get("")
async def list_model_providers(
    kind: ModelKind = "llm",
    user: User = Depends(get_current_user),
) -> dict:
    """List Model Providers. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    providers = providers_for_kind(kind)
    return {"kind": kind, "providers": [provider_payload(p) for p in providers]}


@providers_router.post("/probe")
async def probe_remote_models(
    body: ProbeRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Probe Remote Models. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    provider = get_provider(body.kind, body.provider or None)
    api_base = body.api_base.strip() or provider.default_api_base
    api_key = body.api_key.strip() or store.get_stored_model_api_key_for_probe(
        body.kind, body.provider, api_base
    )

    result = fetch_remote_models(api_key=api_key, api_base=api_base, kind=body.kind)
    if not result.get("ok"):
        err = result.get("error", "fetch_failed")
        messages = {
            "api_key_required": "请填写 API Key",
            "api_key_invalid": "API Key 包含异常字符",
            "api_base_required": "请填写 Base URL",
            "openai_missing": "未安装 openai 依赖",
            "models_empty": "没有获取到模型，请检查 API Key 与 Base URL",
        }
        return {"ok": False, "error": messages.get(str(err), str(err))}
    return result


@providers_router.get("/resolve")
async def resolve_provider_from_settings(
    kind: ModelKind = "llm",
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Resolve Provider From Settings. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    settings = store.get_settings()
    if kind == "llm":
        stored = settings.get("chat_provider") or ""
        base = settings.get("chat_base_url") or ""
    else:
        stored = settings.get("embed_provider") or ""
        base = settings.get("embed_base_url") or ""
    pid = infer_provider_id(kind, base, stored or None)
    return {"kind": kind, "provider": pid}
