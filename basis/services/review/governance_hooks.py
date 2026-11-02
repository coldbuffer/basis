"""Wire Explorer governance decisions from :class:`WorkspaceCoreContext` (no HTTP imports)."""

from __future__ import annotations

from typing import Any

from basis.services.graph.governance.decision import record_governance_decision_for_workspace
from basis.services.kernel import WorkspaceCoreContext


def record_governance_decision_from_context(
    ctx: WorkspaceCoreContext,
    *,
    message: str,
    detail: dict[str, Any] | None = None,
    outcome: str = "approved",
) -> str | None:
    if ctx.runtime_loader is None or ctx.persist_graph is None:
        return None
    return record_governance_decision_for_workspace(
        ctx.workspace.id,
        message=message,
        detail=detail,
        actor_id=ctx.user.id,
        outcome=outcome,
        runtime_loader=ctx.runtime_loader,
        persist_graph=ctx.persist_graph,
    )
