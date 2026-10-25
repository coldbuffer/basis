"""Emit workspace alert episodes for cross-cutting ops events (F-ALT)."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore


def _with_episode(detail: dict[str, Any], episode_key: str) -> dict[str, Any]:
    merged = dict(detail)
    merged["episode_key"] = episode_key
    return merged

def emit_governance_proposal_proposed_alert(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    proposal_id: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    knowledge.create_workspace_alert(
        workspace_id,
        kind="governance.proposal_proposed",
        message=message[:500] or "Ontology proposal submitted for review",
        severity="info",
        detail=_with_episode(
            {"proposal_id": proposal_id, **(detail or {})},
            f"ontology_proposal:{proposal_id}",
        ),
    )


def emit_processing_failed_alert(
    knowledge: KnowledgeStore,
    workspace_id: str,
    job_id: str,
    error_code: str,
    message: str,
) -> None:
    doc_label = job_id[:8]
    try:
        job = knowledge.get_job(workspace_id, job_id)
        if job.subject_type == "document_version" and job.subject_id:
            ctx = knowledge.get_processing_context(workspace_id, job.subject_id)
            doc_label = str(ctx.get("filename") or ctx.get("doc_id") or doc_label)
    except AdminError:
        pass
    code = (error_code or "processing_failed").strip()[:80]
    knowledge.create_workspace_alert(
        workspace_id,
        kind="processing.failed",
        message=f"Processing failed for «{doc_label[:120]}»: {code}",
        severity="warning",
        detail=_with_episode(
            {
                "job_id": job_id,
                "error_code": code,
                "message": (message or "")[:300],
            },
            f"processing:{job_id}",
        ),
    )


def emit_governance_tripped_alert(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    knowledge.create_workspace_alert(
        workspace_id,
        kind="governance.tripped",
        message=message[:500] or "Governance gate blocked the operation",
        severity="warning",
        detail=_with_episode(
            dict(detail or {}),
            _governance_tripped_episode_key(detail or {}),
        ),
    )


def _governance_tripped_episode_key(detail: dict[str, Any]) -> str:
    for key in ("item_id", "proposal_id", "decision_id"):
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return f"governance:{key}:{value.strip()}"
    code = detail.get("code")
    if isinstance(code, str) and code.strip():
        return f"governance:code:{code.strip()}"
    return "governance:tripped"
