"""Drafts, proposals, and versions (Basis stores + bridge for heavy flows)."""

from __future__ import annotations

import asyncio
from typing import Any

from basis.domain.ontology.hub.draft_store import get_draft as get_draft_sync
from basis.domain.ontology.hub.draft_store import list_drafts as list_drafts_sync
from basis.domain.ontology.hub.draft_store import save_draft as save_draft_sync
from basis.domain.ontology.hub.proposal_store import (
    add_proposal_comment as add_proposal_comment_sync,
    approve_proposal as approve_proposal_sync,
    get_proposal as get_proposal_sync,
    list_proposals as list_proposals_sync,
    reject_proposal as reject_proposal_sync,
)
from basis.domain.ontology.hub.proposal_lifecycle import (
    publish_proposal as publish_proposal_sync,
    submit_proposal as submit_proposal_sync,
)
from basis.domain.ontology.hub.version_store import (
    compare_versions as compare_versions_sync,
    list_versions as list_versions_sync,
)


async def save_draft(drafts: dict[str, Any], body: Any) -> Any:
    return save_draft_sync(drafts, body)


async def list_drafts(drafts: dict[str, Any], ontology_uri: str) -> Any:
    return list_drafts_sync(drafts, ontology_uri)


async def get_draft(drafts: dict[str, Any], draft_id: str) -> Any:
    return get_draft_sync(drafts, draft_id)


async def submit_proposal(
    session: Any,
    drafts: dict[str, Any],
    proposals: dict[str, Any],
    body: Any,
) -> Any:
    return await asyncio.to_thread(submit_proposal_sync, session, drafts, proposals, body)


async def list_proposals(
    proposals: dict[str, Any],
    *,
    ontology_uri: str | None = None,
    state: str | None = None,
) -> Any:
    return list_proposals_sync(proposals, ontology_uri=ontology_uri, state=state)


async def get_proposal(proposals: dict[str, Any], proposal_id: str) -> Any:
    return get_proposal_sync(proposals, proposal_id)


async def approve_proposal(proposals: dict[str, Any], proposal_id: str) -> Any:
    return approve_proposal_sync(proposals, proposal_id)


async def reject_proposal(proposals: dict[str, Any], proposal_id: str) -> Any:
    return reject_proposal_sync(proposals, proposal_id)


async def publish_proposal(
    session: Any,
    proposals: dict[str, Any],
    drafts: dict[str, Any],
    versions: dict[str, list[Any]],
    proposal_id: str,
    registry: dict[str, Any] | None = None,
) -> Any:
    return await asyncio.to_thread(
        publish_proposal_sync,
        session,
        proposals,
        drafts,
        versions,
        proposal_id,
        registry,
    )


async def add_proposal_comment(proposals: dict[str, Any], proposal_id: str, body: Any) -> Any:
    return add_proposal_comment_sync(proposals, proposal_id, body)


async def list_versions(versions: dict[str, Any], ontology_uri: str) -> Any:
    return list_versions_sync(versions, ontology_uri)


async def compare_versions(
    session: Any,
    versions: dict[str, list[Any]],
    ontology_uri: str,
    body: Any,
) -> Any:
    return await asyncio.to_thread(compare_versions_sync, session, versions, ontology_uri, body)
