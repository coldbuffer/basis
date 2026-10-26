"""Workspace request context for application operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from basis.domain.graph.projection.projection_lifecycle import GraphProjectionBindings
from basis.domain.graph.session.registry import GraphRuntime
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.search import ChunkSearchService
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.tenancy.admin.admin_types import ApiTokenRecord
from basis.domain.tenancy.admin.store import AdminStore, User, Workspace
from basis.infra.runtime.limits import RuntimeLimits


@dataclass(frozen=True)
class WorkspaceCoreContext:
    workspace: Workspace
    user: User
    knowledge: KnowledgeStore
    store: AdminStore
    chunk_search: ChunkSearchService | None = None
    runtime: GraphRuntime | None = None
    runtime_loader: Callable[[], GraphRuntime] | None = None
    assert_workspace_editor: Callable[[], None] | None = None
    rebuild_projection: Callable[[], Any] | None = None
    clear_projection: Callable[[], None] | None = None
    persist_graph: Callable[[str], None] | None = None
    blob_store: BlobStore | None = None
    projection_bindings: GraphProjectionBindings | None = None
    runtime_limits: RuntimeLimits | None = None
    api_token: ApiTokenRecord | None = None
    # Callable[[fn(access)] -> result]; set from HTTP/MCP when OntologyHubState is available.
    ontology_hub: Callable[[Callable[..., Any]], Any] | None = None

    def graph_runtime(self) -> GraphRuntime:
        if self.runtime is not None:
            return self.runtime
        if self.runtime_loader is None:
            raise RuntimeError("graph runtime is unavailable")
        return self.runtime_loader()


WorkspaceToolContext = WorkspaceCoreContext
