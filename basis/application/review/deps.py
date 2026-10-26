"""Build review resolve dependencies from :class:`WorkspaceCoreContext`."""

from __future__ import annotations

from basis.domain.knowledge.services.review_resolve_approve import ReviewApproveDeps
from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import CoreError


def review_approve_deps(ctx: WorkspaceCoreContext) -> ReviewApproveDeps:
    if ctx.runtime_loader is None or ctx.rebuild_projection is None or ctx.persist_graph is None:
        raise CoreError(
            {"code": "internal_error", "message": "graph runtime unavailable for review approve"},
            status_code=500,
        )
    if ctx.projection_bindings is None or ctx.blob_store is None:
        raise CoreError(
            {
                "code": "internal_error",
                "message": "review approve requires blob store and projection bindings",
            },
            status_code=500,
        )
    return ReviewApproveDeps(
        projection_bindings=ctx.projection_bindings,
        blob_store=ctx.blob_store,
        runtime_loader=ctx.runtime_loader,
        persist_graph=ctx.persist_graph,
        rebuild_projection=ctx.rebuild_projection,
        ontology_hub=ctx.ontology_hub,
    )
