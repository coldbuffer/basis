"""OpenAPI v1 helpers for tests (export from ephemeral app)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from basis.http.openapi.v1_export import (
    export_openapi_v1_document,
    export_openapi_v1_workspaces,
    export_openapi_v1_platform,
)


@lru_cache(maxsize=1)
def _spec_app():
    from basis.app import create_app
    from basis.infra.runtime.config import Settings
    import tempfile
    import uuid

    data_dir = Path(tempfile.gettempdir()) / f"basis-openapi-spec-{uuid.uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=True)
    return create_app(Settings(data_dir=data_dir))


def openapi_v1_full() -> dict[str, Any]:
    return export_openapi_v1_document(_spec_app())


def openapi_v1_platform() -> dict[str, Any]:
    return export_openapi_v1_platform(_spec_app())


def openapi_v1_workspaces() -> dict[str, Any]:
    return export_openapi_v1_workspaces(_spec_app())


def openapi_v1_json(name: str) -> str:
    if name in ("basis-v1.json", "basis-v1.yaml"):
        doc = openapi_v1_full()
    elif name in ("basis-v1-platform.json", "basis-v1-platform.yaml"):
        doc = openapi_v1_platform()
    elif name in (
        "basis-v1-workspaces.json",
        "basis-v1-workspaces.yaml",
    ):
        doc = openapi_v1_workspaces()
    else:
        path = Path(__file__).resolve().parents[4] / "openapi" / name
        if path.is_file():
            doc = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"unknown OpenAPI artifact: {name}")
    return json.dumps(doc, sort_keys=True, ensure_ascii=False)
