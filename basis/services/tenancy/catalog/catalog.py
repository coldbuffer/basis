"""Configured model catalog persisted in settings (JSON + per-model API keys)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

ModelKind = Literal["llm", "embed"]

CATALOG_SETTINGS_KEY = "model_catalog_v1"
MODEL_KEY_PREFIX = "model_api_key:"


def empty_catalog() -> dict[str, list[dict[str, Any]]]:
    return {"llm": [], "embed": []}


def parse_catalog(raw: str | None) -> dict[str, list[dict[str, Any]]]:
    if not raw:
        return empty_catalog()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return empty_catalog()
    if not isinstance(data, dict):
        return empty_catalog()
    out = empty_catalog()
    for kind in ("llm", "embed"):
        items = data.get(kind)
        if isinstance(items, list):
            out[kind] = [item for item in items if isinstance(item, dict) and item.get("id")]
    return out


def serialize_catalog(catalog: dict[str, list[dict[str, Any]]]) -> str:
    return json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))


def new_entry(
    kind: ModelKind,
    *,
    provider: str,
    api_base: str,
    model: str,
    display_name: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    model_id = model.strip()
    return {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "provider": provider.strip(),
        "api_base": api_base.strip().rstrip("/"),
        "model": model_id,
        "display_name": (display_name or model_id).strip(),
        "enabled": enabled,
    }


def model_secret_key(entry_id: str) -> str:
    return f"{MODEL_KEY_PREFIX}{entry_id}"


def find_entry(catalog: dict[str, list[dict[str, Any]]], entry_id: str) -> tuple[ModelKind, int, dict[str, Any]] | None:
    for kind in ("llm", "embed"):
        for index, item in enumerate(catalog.get(kind, [])):
            if item.get("id") == entry_id:
                return kind, index, item
    return None
