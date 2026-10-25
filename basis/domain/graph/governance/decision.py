"""Record Explorer graph decisions when governance gates trip (F-GOV-07)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.graph.session.registry import GraphRuntime
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.knowledge.services.alerts_emit import emit_governance_tripped_alert
from basis.domain.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

_GOVERNANCE_ALERT_CODE_TOKENS = ("governance", "impact", "tripped", "shacl")


def admin_error_triggers_governance_alert(code: str) -> bool:
    """True when an Explorer/AdminError code should emit `governance.tripped`."""
    normalized = code.lower()
    return any(token in normalized for token in _GOVERNANCE_ALERT_CODE_TOKENS)


_SKIP_GOVERNANCE_ALERT_ON_REVIEW_APPROVE = frozenset(
    {"review_closed", "not_found", "forbidden", "unsupported_review_kind"},
)


def should_emit_governance_tripped_on_review_approve(code: str) -> bool:
    """Emit only when approve failed due to governance/impact/SHACL gates (F-GOV-05)."""
    if code in _SKIP_GOVERNANCE_ALERT_ON_REVIEW_APPROVE:
        return False
    return admin_error_triggers_governance_alert(code)


def maybe_emit_governance_tripped_for_admin_error(
    workspace_id: str,
    knowledge: KnowledgeStore,
    exc: AdminError,
    *,
    detail: dict[str, Any] | None = None,
    actor_id: str | None = None,
    runtime_loader: Callable[[], GraphRuntime] | None = None,
    persist_graph: Callable[[str], None] | None = None,
) -> None:
    """Emit `governance.tripped` when an AdminError reflects a governance gate (F-GOV-05)."""
    if not admin_error_triggers_governance_alert(exc.code):
        return
    payload = {"code": exc.code, **(detail or {})}
    emit_governance_tripped_for_workspace(
        workspace_id,
        knowledge,
        message=exc.message,
        detail=payload,
        actor_id=actor_id,
        runtime_loader=runtime_loader,
        persist_graph=persist_graph,
    )


def maybe_emit_governance_tripped_on_review_approve(
    workspace_id: str,
    knowledge: KnowledgeStore,
    *,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
    actor_id: str | None = None,
    runtime_loader: Callable[[], GraphRuntime] | None = None,
    persist_graph: Callable[[str], None] | None = None,
) -> None:
    """Review approve failure: emit only for governance/impact/SHACL gates (F-GOV-05)."""
    if not should_emit_governance_tripped_on_review_approve(code):
        return
    payload = {"code": code, **(detail or {})}
    emit_governance_tripped_for_workspace(
        workspace_id,
        knowledge,
        message=message,
        detail=payload,
        actor_id=actor_id,
        runtime_loader=runtime_loader,
        persist_graph=persist_graph,
    )


def _try_record_governance_decision(
    workspace_id: str,
    *,
    message: str,
    detail: dict[str, Any],
    actor_id: str | None,
    outcome: str = "blocked",
    category: str = "governance",
    reasoning: str | None = None,
    runtime_loader: Callable[[], GraphRuntime] | None = None,
    persist_graph: Callable[[str], None] | None = None,
) -> str | None:
    if runtime_loader is None or persist_graph is None:
        return None
    try:
        runtime = runtime_loader()
        session = require_graph_session(runtime)
        graph = session.graph
        if not hasattr(graph, "record_decision"):
            return None
        review_item_id = detail.get("review_item_id") or detail.get("item_id")
        metadata = {**detail}
        if review_item_id:
            metadata["review_item_id"] = review_item_id
        if "alert_kind" not in metadata and category == "governance":
            metadata.setdefault("alert_kind", "governance.tripped")
        reasoning_text = (
            reasoning if reasoning is not None else json.dumps(detail, default=str)
        )[:4000]
        entities: list[dict[str, Any]] = []
        primary_id = detail.get("primary_id")
        duplicate_ids = detail.get("duplicate_ids")
        if isinstance(primary_id, str) and primary_id.strip():
            entities.append({"id": primary_id.strip(), "role": "primary"})
        if isinstance(duplicate_ids, list):
            for dup in duplicate_ids:
                if isinstance(dup, str) and dup.strip():
                    entities.append({"id": dup.strip(), "role": "duplicate"})
        decision_id = graph.record_decision(
            category=category,
            scenario=(message or "Governance gate blocked")[:500],
            reasoning=reasoning_text,
            outcome=outcome,
            confidence=1.0,
            entities=entities,
            decision_maker=actor_id,
            metadata=metadata,
        )
        persist_graph(workspace_id)
        return str(decision_id)
    except Exception:
        logger.debug("governance decision record skipped", exc_info=True)
        return None


def record_governance_decision_for_workspace(
    workspace_id: str,
    *,
    message: str,
    detail: dict[str, Any] | None = None,
    actor_id: str | None = None,
    outcome: str = "approved",
    category: str = "governance",
    reasoning: str | None = None,
    runtime_loader: Callable[[], GraphRuntime] | None = None,
    persist_graph: Callable[[str], None] | None = None,
) -> str | None:
    """Persist an Explorer graph decision (e.g. review approve). Returns id or None."""
    return _try_record_governance_decision(
        workspace_id,
        message=message,
        detail=dict(detail or {}),
        actor_id=actor_id,
        outcome=outcome,
        category=category,
        reasoning=reasoning,
        runtime_loader=runtime_loader,
        persist_graph=persist_graph,
    )


def emit_governance_tripped_for_workspace(
    workspace_id: str,
    knowledge: KnowledgeStore,
    *,
    message: str,
    detail: dict[str, Any] | None = None,
    actor_id: str | None = None,
    runtime_loader: Callable[[], GraphRuntime] | None = None,
    persist_graph: Callable[[str], None] | None = None,
) -> str | None:
    payload = dict(detail or {})
    decision_id = _try_record_governance_decision(
        workspace_id,
        message=message,
        detail=payload,
        actor_id=actor_id,
        runtime_loader=runtime_loader,
        persist_graph=persist_graph,
    )
    if decision_id:
        payload["decision_id"] = decision_id
    emit_governance_tripped_alert(knowledge, workspace_id, message=message, detail=payload)
    return decision_id
