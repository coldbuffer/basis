"""Shared helpers for workspace ingest source routes."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def doc_id_from_external_key(external_key: str | None, title: str) -> str:
    if external_key and external_key.strip():
        return external_key.strip()
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", (title or "ingest").strip()).strip("-._")
    return stem or f"ingest-{uuid.uuid4().hex[:12]}"


def webhook_path(workspace_id: str, source_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/sources/{source_id}/webhook"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
