"""Build `WorkspaceCoreContext` for HTTP handlers."""

from __future__ import annotations

from fastapi import Request

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_api_token_record,
    graph_runtime_for,
    get_blob_store,
    get_chunk_search,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_runtime_limits,
    get_store,
    graph_projection_bindings,
    drop_graph,
    rebuild_graph_projection,
    save_graph,
)
from basis.application.kernel import WorkspaceCoreContext
from basis.application.ontology.hub_access import OntologyHubAccess
from basis.domain.ontology.hub.scoped_state import OntologyHubState
from basis.domain.graph.session.guard import require_graph_session


def build_workspace_core_context(
    request: Request,
    *,
    workspace_id: str,
    user: User,
    store: AdminStore | None = None,
    require_editor: bool = False,
) -> WorkspaceCoreContext:
    store = store or get_store(request)
    if require_editor:
        workspace, _role = get_workspace_for_editor(request, user, workspace_id, store)
    else:
        workspace, _role = get_workspace_for_viewer(request, user, workspace_id, store)

    def _ontology_hub_runner(fn):
        with OntologyHubState(request, workspace_id):
            session = require_graph_session(graph_runtime_for(request, workspace_id))
            app_state = request.app.state
            access = OntologyHubAccess(
                workspace_id=workspace_id,
                registry=app_state.ontology_registries[workspace_id],
                drafts=app_state.ontology_drafts[workspace_id],
                proposals=app_state.ontology_proposals[workspace_id],
                versions=app_state.ontology_versions[workspace_id],
                graph_session=session,
                persist_hub=lambda: save_graph(request, workspace_id, sync_ledger=False),
            )
            return fn(access)

    return WorkspaceCoreContext(
        workspace=workspace,
        user=user,
        knowledge=get_knowledge_store(request),
        store=store,
        chunk_search=get_chunk_search(request),
        runtime_loader=lambda: graph_runtime_for(request, workspace_id),
        assert_workspace_editor=lambda: get_workspace_for_editor(request, user, workspace_id, store),
        rebuild_projection=lambda: rebuild_graph_projection(request, workspace_id),
        clear_projection=lambda: drop_graph(request, workspace_id),
        persist_graph=lambda kid: save_graph(request, kid),
        blob_store=get_blob_store(request),
        projection_bindings=graph_projection_bindings(request),
        runtime_limits=get_runtime_limits(request),
        api_token=get_api_token_record(request),
        ontology_hub=_ontology_hub_runner,
    )
