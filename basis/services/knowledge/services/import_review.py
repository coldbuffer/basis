"""Helpers for staged graph import review items."""

from __future__ import annotations

import io
from typing import Any

from fastapi import UploadFile

from basis.services.errors import AdminError
from basis.services.knowledge.blob_store import BlobStore

from basis.infra.runtime.limits import IMPORT_MAX_BYTES as _DEFAULT_IMPORT_MAX_BYTES
_ALLOWED_EXTENSIONS = frozenset({".json", ".csv"})


def validate_import_filename(filename: str | None) -> str:
    base = filename or "import.json"
    lower = base.lower()
    if not any(lower.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise AdminError(
            422,
            "bad_import_format",
            f"不支持的导入格式，仅允许 {sorted(_ALLOWED_EXTENSIONS)}",
        )
    return base


def stage_import_blob(
    blob_store: BlobStore,
    workspace_id: str,
    data: bytes,
    filename: str,
    *,
    max_bytes: int = _DEFAULT_IMPORT_MAX_BYTES,
) -> dict[str, Any]:
    cap = max(1, max_bytes)
    if len(data) > cap:
        raise AdminError(
            413,
            "import_too_large",
            f"导入文件超过 {cap // (1024 * 1024)} MB 限制",
        )
    safe_name = validate_import_filename(filename)
    ref = blob_store.put(workspace_id, data)
    return {
        "filename": safe_name,
        "blob_key": ref.blob_key,
        "sha256": ref.sha256,
        "byte_size": ref.byte_size,
    }


def discard_staged_import(blob_store: BlobStore, workspace_id: str, payload: dict[str, Any]) -> None:
    blob_key = payload.get("blob_key")
    if not blob_key:
        return
    try:
        blob_store.delete(workspace_id, str(blob_key))
    except AdminError:
        pass


def upload_file_from_staged(blob_store: BlobStore, workspace_id: str, payload: dict[str, Any]) -> UploadFile:
    blob_key = payload.get("blob_key")
    if not blob_key:
        raise AdminError(422, "bad_review_payload", "导入审核项缺少 blob_key")
    data = blob_store.read(workspace_id, str(blob_key))
    filename = str(payload.get("filename") or "import.json")
    return UploadFile(file=io.BytesIO(data), filename=filename)
