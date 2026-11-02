"""Shared application primitives: context, errors, workspace gates."""

from __future__ import annotations

from basis.services.kernel.context import WorkspaceCoreContext, WorkspaceToolContext
from basis.services.kernel.errors import CoreError
from basis.services.kernel.limits import chunk_search_limit_max, graph_search_max_limit
from basis.services.kernel.workspace_gate import require_workspace_editor, require_workspace_owner

__all__ = [
    "CoreError",
    "WorkspaceCoreContext",
    "WorkspaceToolContext",
    "chunk_search_limit_max",
    "graph_search_max_limit",
    "require_workspace_editor",
    "require_workspace_owner",
]
