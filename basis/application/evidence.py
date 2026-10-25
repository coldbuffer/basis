"""Optional ledger evidence helpers for application / MCP tools."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.domain.errors import AdminError
from basis.domain.knowledge.evidence import quote_from_chunk, resolve_workspace_chunk


def optional_chunk_id(args: dict[str, Any]) -> str | None:
    raw = args.get("chunk_id")
    if raw is None:
        return None
    cid = str(raw).strip()
    return cid or None


def optional_quote(args: dict[str, Any]) -> str | None:
    raw = args.get("quote")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def admin_error_dict(exc: AdminError) -> dict[str, str]:
    return {"error": exc.code, "message": exc.message}


def merge_graph_evidence_metadata(
    metadata: dict[str, Any] | None,
    *,
    chunk_id: str | None,
    quote: str | None,
) -> dict[str, Any]:
    base = dict(metadata or {})
    if not chunk_id:
        return base
    evidence: dict[str, Any] = {"chunk_id": chunk_id}
    if quote:
        evidence["quote"] = quote
    base["basis_evidence"] = evidence
    return base


def validate_chunk_for_ctx(ctx: WorkspaceCoreContext, chunk_id: str) -> dict[str, Any]:
    try:
        return resolve_workspace_chunk(ctx.knowledge, ctx.workspace.id, chunk_id)
    except AdminError as exc:
        raise exc


def optional_evidence_attestation(
    ctx: WorkspaceCoreContext,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """Resolve optional chunk_id/quote to {chunk_id, quote} or an error payload."""
    chunk_id = optional_chunk_id(args)
    if not chunk_id:
        return None, None
    quote = optional_quote(args)
    try:
        row = resolve_workspace_chunk(ctx.knowledge, ctx.workspace.id, chunk_id)
    except AdminError as exc:
        return None, admin_error_dict(exc)
    return {"chunk_id": chunk_id, "quote": quote_from_chunk(row, override=quote)}, None


def optional_metadata_with_evidence(
    ctx: WorkspaceCoreContext,
    args: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, str] | None]:
    attestation, err = optional_evidence_attestation(ctx, args)
    if err:
        return None, None, err
    if not attestation:
        return metadata, None, None
    merged = merge_graph_evidence_metadata(
        metadata,
        chunk_id=attestation["chunk_id"],
        quote=attestation.get("quote"),
    )
    return merged, attestation, None


def resolve_extract_text(
    ctx: WorkspaceCoreContext,
    args: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Resolve NER/extract input text; optional chunk_id supplies body and evidence."""
    text = str(args.get("text") or "").strip()
    attestation, err = optional_evidence_attestation(ctx, args)
    if err:
        return None, err
    if attestation and not text:
        row = resolve_workspace_chunk(ctx.knowledge, ctx.workspace.id, attestation["chunk_id"])
        text = str(row.get("text") or "").strip()
    if not text:
        return None, {"error": "text or chunk_id is required"}
    return text, attestation or {}
