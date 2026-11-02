"""Ontology editor drafts (explicit per-workspace store, no Explorer routes)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from basis.services.errors import AdminError

logger = logging.getLogger(__name__)


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _diff_payload(diff: Any) -> Any:
    if hasattr(diff, "model_dump"):
        return diff.model_dump()
    return diff


def save_draft(drafts: dict[str, Any], body: Any) -> dict[str, Any]:
    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        from semantica.change_management.change_log import ChangeLogEntry

        ChangeLogEntry.create_now(
            author=getattr(body, "author", None),
            description=getattr(body, "summary", None) or f"Draft changes for {body.ontology_uri}",
            change_id=draft_id,
        )
    except Exception as exc:
        logger.warning("Failed to create ChangeLogEntry: %s", exc)

    record = {
        "draft_id": draft_id,
        "ontology_uri": body.ontology_uri,
        "diff": _diff_payload(body.diff),
        "author": body.author,
        "summary": body.summary,
        "created_at": now,
        "updated_at": now,
    }
    try:
        from basis.services.ontology.models import DraftResponse

        drafts[draft_id] = DraftResponse.model_validate(record)
    except Exception:
        drafts[draft_id] = record
    return _dump(drafts[draft_id])


def list_drafts(drafts: dict[str, Any], ontology_uri: str) -> list[dict[str, Any]]:
    return [
        _dump(draft)
        for draft in drafts.values()
        if _dump(draft).get("ontology_uri") == ontology_uri
    ]


def get_draft(drafts: dict[str, Any], draft_id: str) -> dict[str, Any]:
    if draft_id not in drafts:
        raise AdminError(404, "not_found", "Draft not found.")
    return _dump(drafts[draft_id])
