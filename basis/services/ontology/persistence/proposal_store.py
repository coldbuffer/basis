"""Ontology change proposals — list/get/approve/reject/comment (no Explorer routes)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from basis.services.errors import AdminError


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _get_field(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _set_field(record: Any, key: str, value: Any) -> None:
    if isinstance(record, dict):
        record[key] = value
    else:
        setattr(record, key, value)


def _touch(record: Any) -> None:
    _set_field(record, "updated_at", datetime.now(timezone.utc).isoformat())


def list_proposals(
    proposals: dict[str, Any],
    *,
    ontology_uri: str | None = None,
    state: str | None = None,
) -> list[dict[str, Any]]:
    rows = [_dump(proposal) for proposal in proposals.values()]
    if ontology_uri:
        rows = [row for row in rows if row.get("ontology_uri") == ontology_uri]
    if state:
        rows = [row for row in rows if row.get("state") == state]
    return rows


def get_proposal(proposals: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    if proposal_id not in proposals:
        raise AdminError(404, "not_found", "Proposal not found.")
    return _dump(proposals[proposal_id])


def approve_proposal(proposals: dict[str, Any], proposal_id: str) -> dict[str, str]:
    if proposal_id not in proposals:
        raise AdminError(404, "not_found", "Proposal not found.")
    proposal = proposals[proposal_id]
    _set_field(proposal, "state", "approved")
    _touch(proposal)
    return {"status": "approved", "proposal_id": proposal_id}


def reject_proposal(proposals: dict[str, Any], proposal_id: str) -> dict[str, str]:
    if proposal_id not in proposals:
        raise AdminError(404, "not_found", "Proposal not found.")
    proposal = proposals[proposal_id]
    _set_field(proposal, "state", "rejected")
    _touch(proposal)
    return {"status": "rejected", "proposal_id": proposal_id}


def add_proposal_comment(
    proposals: dict[str, Any],
    proposal_id: str,
    body: Any,
) -> dict[str, str]:
    if proposal_id not in proposals:
        raise AdminError(404, "not_found", "Proposal not found.")
    proposal = proposals[proposal_id]
    comment = {
        "id": f"comment_{uuid.uuid4().hex[:8]}",
        "element_uri": body.element_uri,
        "text": body.text,
        "author": body.author,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    comments = _get_field(proposal, "comments", []) or []
    if isinstance(proposal, dict):
        proposal["comments"] = [*comments, comment]
    else:
        proposal.comments.append(comment)
    _touch(proposal)
    return {"status": "commented", "comment_id": comment["id"]}
