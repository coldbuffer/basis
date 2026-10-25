"""Workspace chunk citations for ledger statements and graph metadata."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore


def resolve_workspace_chunk(
    knowledge: KnowledgeStore,
    workspace_id: str,
    chunk_id: str,
) -> dict[str, Any]:
    cid = chunk_id.strip()
    if not cid:
        raise AdminError(422, "validation_error", "chunk_id is empty")
    row = knowledge.get_chunk(workspace_id, cid)
    if row is None:
        raise AdminError(404, "chunk_not_found", f"Chunk '{cid}' not found in this workspace")
    return row


def quote_from_chunk(row: dict[str, Any], *, override: str | None = None, fallback: str = "") -> str:
    if override is not None and str(override).strip():
        text = str(override).strip()
    else:
        text = str(row.get("text") or fallback or "").strip()
    if len(text) <= 512:
        return text
    return text[:509] + "..."
