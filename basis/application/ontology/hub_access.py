"""Ontology hub stores + graph session for application/MCP operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from basis.application.kernel import WorkspaceCoreContext
from basis.domain.errors import AdminError


@dataclass(frozen=True)
class OntologyHubAccess:
    workspace_id: str
    registry: dict[str, Any]
    drafts: dict[str, Any]
    proposals: dict[str, Any]
    versions: dict[str, Any]
    alignments: dict[str, Any]
    graph_session: Any
    persist_hub: Callable[[], None]


def run_ontology_hub(
    ctx: WorkspaceCoreContext,
    fn: Callable[[OntologyHubAccess], dict[str, Any]],
) -> dict[str, Any]:
    runner = ctx.ontology_hub
    if runner is None:
        return {
            "error": "ontology_hub_unavailable",
            "message": "Ontology hub is only available in server HTTP/MCP context.",
        }
    try:
        return runner(fn)
    except AdminError as exc:
        return {"error": exc.code, "message": exc.message}
