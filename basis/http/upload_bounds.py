"""Bounded reads for multipart uploads (X-04)."""

from __future__ import annotations

from fastapi import UploadFile

from basis.services.errors import AdminError

_READ_CHUNK = 1024 * 1024


def ensure_payload_bytes(
    size: int,
    max_bytes: int,
    *,
    code: str = "upload_too_large",
    label: str = "上传",
) -> None:
    cap = max(1, max_bytes)
    if size > cap:
        raise AdminError(
            413,
            code,
            f"{label}超过 {cap // (1024 * 1024)} MB 限制",
        )


async def read_bounded_upload(file: UploadFile, max_bytes: int) -> bytes:
    cap = max(1, max_bytes)
    parts: list[bytes] = []
    total = 0
    while True:
        piece = await file.read(_READ_CHUNK)
        if not piece:
            break
        total += len(piece)
        if total > cap:
            raise AdminError(
                413,
                "upload_too_large",
                f"上传超过 {cap // (1024 * 1024)} MB 限制",
            )
        parts.append(piece)
    return b"".join(parts)
