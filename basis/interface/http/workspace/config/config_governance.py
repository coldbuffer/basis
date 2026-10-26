"""Workspace governance governor (F-GOV-04 Phase A)."""

from __future__ import annotations

from typing import Any

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.knowledge.services.governor import run_governor_pass
from basis.interface.http.workspace.review.conflict_scan_http import build_conflict_scan_context
from basis.domain.knowledge.services.governor_graph_dedup import (
    DEFAULT_GOVERNOR_DEDUP_THRESHOLD,
    scan_graph_semantic_dedup_clusters,
)
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.shared.deps import (
    get_current_user,
    graph_runtime_for,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_store,
)

router = APIRouter(tags=["workspaces"])


class GovernanceConfigRequest(BaseModel):
    governor_enabled: bool = False
    governor_interval_minutes: int = Field(default=1440, ge=0, le=10_080)
    governor_confidence_min: float = Field(default=0.75, ge=0.0, le=1.0)
    governance_ontology_uri: str | None = Field(
        default=None,
        description="Ontology URI for Hub SHACL during conflict scans (empty clears).",
    )
    entity_type_surface_phrases: list[str] | None = Field(
        default=None,
        description=(
            "Relation phrases treated as rdf:type for class mapping scans "
            "(e.g. 是, is_a). Omit to keep stored value; empty list clears override."
        ),
    )


class GovernanceShaclRequest(BaseModel):
    ontology_uri: str = Field(description="Ontology URI these shapes apply to (also sets scan URI).")
    shacl_turtle: str = Field(
        default="",
        description="Persisted SHACL Turtle for governance scans (empty clears saved shapes).",
    )

class GovernorRunRequest(BaseModel):
    confidence_min: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override default governor confidence threshold (0.75).",
    )
    dedup_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Graph semantic dedup similarity threshold (default 0.8).",
    )
    include_shacl: bool = Field(default=True, description="Run SHACL violation scan (mapped ledger facts).")
    include_low_confidence: bool = Field(
        default=True,
        description="Enqueue active statements below confidence_min.",
    )
    include_entity_label_clusters: bool = Field(
        default=True,
        description="Enqueue ledger entities sharing the same canonical label.",
    )
    include_graph_dedup: bool = Field(
        default=True,
        description="Enqueue graph semantic duplicate pairs (requires graph runtime).",
    )


@router.post("/{workspace_id}/governance/governor/run")
async def governance_governor_run(
    workspace_id: str,
    request: Request,
    body: GovernorRunRequest | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Governance Governor Run. Batch conflict scan and low-confidence review enqueue (F-GOV-04). Requires workspace editor+.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    req = body or GovernorRunRequest()
    if not any(
        (
            req.include_shacl,
            req.include_low_confidence,
            req.include_entity_label_clusters,
            req.include_graph_dedup,
        )
    ):
        raise AdminError(422, "governor_scan_empty", "至少选择一项治理扫描范围")
    confidence_min = req.confidence_min
    dedup_threshold = (
        req.dedup_threshold if req.dedup_threshold is not None else DEFAULT_GOVERNOR_DEDUP_THRESHOLD
    )
    scan_ctx = build_conflict_scan_context(request, workspace_id, knowledge)
    result = run_governor_pass(
        knowledge,
        workspace_id,
        confidence_min=confidence_min,
        scan_ctx=scan_ctx,
        include_shacl=req.include_shacl,
        include_low_confidence=req.include_low_confidence,
        include_entity_label_clusters=req.include_entity_label_clusters,
    )
    graph_dedup: dict[str, Any] = {"created": 0, "skipped": 0}
    if req.include_graph_dedup:
        try:
            runtime = graph_runtime_for(request, workspace_id)
            session = require_graph_session(runtime)
            graph_dedup = await scan_graph_semantic_dedup_clusters(
                knowledge,
                workspace_id,
                session,
                threshold=dedup_threshold,
            )
        except AdminError as exc:
            if exc.code == "graph_runtime_unavailable":
                graph_dedup = {**graph_dedup, "unavailable": True}
            else:
                raise
    result = {**result, "graph_dedup_clusters": graph_dedup, "dedup_threshold": dedup_threshold}
    knowledge.touch_governor_last_run(workspace_id, datetime.now(timezone.utc).isoformat())
    return result


@router.get("/{workspace_id}/governance/config")
async def get_governance_config(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Governance Config. Per-workspace governor schedule and confidence threshold (F-GOV-04). Requires workspace viewer+.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    config = knowledge.get_governance_config(workspace_id)
    return {"config": config.public_dict()}


@router.put("/{workspace_id}/governance/config")
async def update_governance_config(
    workspace_id: str,
    request: Request,
    body: GovernanceConfigRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Governance Config Update. Enable scheduled governor passes (requires BASIS_GOVERNOR_TICK_SECONDS). Requires workspace admin.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    try:
        config = knowledge.update_governance_config(
            workspace_id,
            governor_enabled=body.governor_enabled,
            governor_interval_minutes=body.governor_interval_minutes,
            governor_confidence_min=body.governor_confidence_min,
            governance_ontology_uri=body.governance_ontology_uri,
            clear_governance_ontology_uri=body.governance_ontology_uri == "",
            entity_type_surface_phrases=body.entity_type_surface_phrases,
        )
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc
    return {"config": config.public_dict()}


@router.put("/{workspace_id}/governance/shacl")
async def update_governance_shacl(
    workspace_id: str,
    request: Request,
    body: GovernanceShaclRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Governance Shacl. Persist workspace SHACL Turtle for conflict scans (paired with ontology URI). Requires workspace editor+.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    config = knowledge.save_governance_shacl(
        workspace_id,
        ontology_uri=body.ontology_uri,
        shacl_turtle=body.shacl_turtle,
    )
    return {"config": config.public_dict()}
