"""Workspace ContextGraph access for Semantica-aligned MCP tools."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.domain.errors import AdminError


def context_graph(ctx: WorkspaceCoreContext) -> Any:
    runtime = ctx.graph_runtime()
    return runtime.basis.graph


def persist_graph_session(ctx: WorkspaceCoreContext) -> None:
    if ctx.persist_graph is not None:
        ctx.persist_graph(ctx.workspace.id)


def require_graph_mutation(ctx: WorkspaceCoreContext) -> Any:
    from basis.application.kernel.workspace_gate import require_workspace_editor

    require_workspace_editor(ctx)
    graph = context_graph(ctx)
    return graph
