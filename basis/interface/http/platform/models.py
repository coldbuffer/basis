from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import get_current_user, get_store, require_system_admin

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
