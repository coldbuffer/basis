"""Review queue approve orchestration (HTTP / MCP)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from basis.domain.errors import AdminError
from basis.domain.graph.governance.decision import record_governance_decision_for_workspace
from basis.domain.graph.governance.review_decision_record import (
    build_entity_cluster_promote_decision,
    build_entity_merge_decision,
)
from basis.domain.graph.governance.enrich_write import merge_nodes
from basis.domain.graph.reads.import_write import import_graph_file
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.graph.session.registry import GraphRuntime
from basis.domain.graph.projection.projection_lifecycle import GraphProjectionBindings
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.ports.platform import WorkspaceAuditActor, WorkspaceAuditStore
from basis.domain.knowledge.services.conflict_review import (
    SHACL_VIOLATION_KIND,
    run_shacl_conflict_scan,
)

from basis.domain.knowledge.services.governor import LOW_CONFIDENCE_KIND, resolve_low_confidence_approve
from basis.domain.knowledge.services.governor_cluster import ENTITY_CLUSTER_KIND
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.services.import_review import (
    discard_staged_import,
    upload_file_from_staged,
)
from basis.domain.ontology.mappings.service import (
    MAPPING_REVIEW_KIND,
    apply_mapping_status_change,
)
from basis.domain.knowledge.services.remember_service import STATEMENT_REVIEW_KIND
from basis.domain.knowledge.services.review_resolve import approve_statement_remember_review
from basis.domain.knowledge.store import KnowledgeStore


def ledger_entity_merge_ids(
    knowledge: KnowledgeStore,
    workspace_id: str,
    primary_id: str,
    duplicate_ids: list[str],
) -> bool:
    if not primary_id or not duplicate_ids:
        return False
    if not knowledge.ledger_entity_exists(workspace_id, primary_id):
        return False
    return all(knowledge.ledger_entity_exists(workspace_id, dup) for dup in duplicate_ids)


@dataclass(frozen=True)
class ReviewApproveDeps:
    projection_bindings: GraphProjectionBindings | None
    blob_store: BlobStore | None
    runtime_loader: Callable[[], GraphRuntime]
    persist_graph: Callable[[str], None]
    rebuild_projection: Callable[[], dict[str, Any]]



async def approve_review_item(
    *,
    knowledge: KnowledgeStore,
    store: WorkspaceAuditStore,
    user: WorkspaceAuditActor,
    workspace_id: str,
    item_id: str,
    rationale: str | None,
    primary_id_override: str | None,
    deps: ReviewApproveDeps,
) -> dict[str, Any]:
    item = knowledge.get_review_item(workspace_id, item_id)
    if item["status"] != "open":
        raise AdminError(409, "review_closed", "审核项已处理")

    merge_result: dict[str, Any] | None = None
    import_result: dict[str, Any] | None = None
    mapping_result: dict[str, Any] | None = None
    decision_id: str | None = None
    approve_action = "workspace.graph.merge_approved"

    if item["kind"] == MAPPING_REVIEW_KIND:
        approve_action = "workspace.mapping.approved"
        payload = item["payload"] or {}
        mapping_id = str(payload.get("mapping_id") or item["subject_id"])
        mapping_result = apply_mapping_status_change(
            workspace_id,
            mapping_id,
            user,
            store,
            knowledge,
            status="confirmed",
            why=rationale,
            sync_review=False,
            projection_bindings=deps.projection_bindings,
        )
        mapping_result = {
            **mapping_result,
            "shacl_scan": run_shacl_conflict_scan(knowledge, workspace_id),
        }
    elif item["kind"] == "entity_merge":
        payload = item["payload"]
        primary_id = str(payload.get("primary_id") or "")
        duplicate_ids = [str(d) for d in payload.get("duplicate_ids") or []]

        if ledger_entity_merge_ids(knowledge, workspace_id, primary_id, duplicate_ids):
            ledger_merges = [
                knowledge.record_entity_merge(
                    workspace_id,
                    source_entity_id=dup,
                    target_entity_id=primary_id,
                    actor_id=user.id,
                    why=rationale,
                    decision_id=decision_id,
                )
                for dup in duplicate_ids
            ]
            projection = deps.rebuild_projection()
            merge_result = {
                "mode": "ledger_rebuild",
                "ledger_merges": ledger_merges,
                "projection": projection,
            }
        else:
            from basis.domain.knowledge.services.graph_sync import resolve_ledger_entity_id

            runtime = deps.runtime_loader()
            session = require_graph_session(runtime)
            primary_ledger = resolve_ledger_entity_id(
                knowledge, workspace_id, runtime.basis, primary_id
            )
            ledger_merges = []
            if primary_ledger:
                for dup in duplicate_ids:
                    if dup != primary_ledger and knowledge.ledger_entity_exists(workspace_id, dup):
                        ledger_merges.append(
                            knowledge.record_entity_merge(
                                workspace_id,
                                source_entity_id=dup,
                                target_entity_id=primary_ledger,
                                actor_id=user.id,
                                why=rationale,
                                decision_id=decision_id,
                            )
                        )
            merge_result = await asyncio.to_thread(
                merge_nodes,
                session,
                primary_id=str(payload.get("primary_id") or primary_id),
                duplicate_ids=[str(d) for d in duplicate_ids],
            )
            deps.persist_graph(workspace_id)
            if ledger_merges:
                merge_result = {**merge_result, "ledger_merges": ledger_merges}
            elif duplicate_ids:
                merge_result = {
                    **merge_result,
                    "ledger_notice": "graph_only_merge",
                    "ledger_skipped_ids": duplicate_ids,
                }
            merged_sources = {row["source_entity_id"] for row in ledger_merges}
            partial = [
                dup
                for dup in duplicate_ids
                if primary_ledger and dup != primary_ledger and dup not in merged_sources
            ]
            if ledger_merges and partial:
                merge_result = {
                    **merge_result,
                    "ledger_notice": "partial_ledger",
                    "ledger_skipped_ids": partial,
                }
        scenario, reasoning_text, merge_detail = build_entity_merge_decision(
            knowledge,
            workspace_id,
            review_item_id=item_id,
            primary_id=primary_id,
            duplicate_ids=duplicate_ids,
            rationale=rationale,
            merge_result=merge_result,
        )
        graph_decision_id = record_governance_decision_for_workspace(
            workspace_id,
            message=scenario,
            detail=merge_detail,
            reasoning=reasoning_text,
            category="merge",
            actor_id=user.id,
            runtime_loader=lambda: deps.runtime_loader(),
            persist_graph=lambda kid: deps.persist_graph(kid),
        )
        agent_decision_id = knowledge.record_agent_decision(
            workspace_id,
            action="approve_entity_merge",
            review_item_id=item_id,
            rationale=rationale,
            trace={
                "primary_id": primary_id,
                "duplicate_ids": duplicate_ids,
                "graph_decision_id": graph_decision_id,
            },
        )
        decision_id = graph_decision_id or agent_decision_id
    elif item["kind"] == STATEMENT_REVIEW_KIND:
        decision_id = record_governance_decision_for_workspace(
            workspace_id,
            message="Review approve: statement_remember",
            detail={"item_id": item_id},
            actor_id=user.id,
            runtime_loader=lambda: deps.runtime_loader(),
            persist_graph=lambda kid: deps.persist_graph(kid),
        )
        audit_extra = {"decision_id": decision_id} if decision_id else None
        result = approve_statement_remember_review(
            knowledge=knowledge,
            store=store,
            user=user,
            workspace_id=workspace_id,
            item_id=item_id,
            rationale=rationale,
            rebuild_projection=lambda: deps.rebuild_projection(),
            audit_extra=audit_extra,
        )
        return {
            "item": result["item"],
            "merge": result.get("merge"),
            "import": None,
            "mapping": None,
            "decision_id": decision_id,
        }
    elif item["kind"] == ENTITY_CLUSTER_KIND:
        payload = dict(item.get("payload") or {})
        entity_ids = list(payload.get("entity_ids") or [])
        primary_id = str(
            primary_id_override
            or payload.get("suggested_primary_id")
            or (entity_ids[0] if entity_ids else "")
        )
        duplicate_ids = [eid for eid in entity_ids if eid != primary_id]
        if not primary_id or not duplicate_ids:
            raise AdminError(422, "bad_cluster", "实体聚类无效")
        subject_id = KnowledgeStore.merge_review_subject_key(primary_id, duplicate_ids)
        merge_item = knowledge.create_review_item(
            workspace_id,
            kind="entity_merge",
            subject_type="graph_nodes",
            subject_id=subject_id,
            payload={"primary_id": primary_id, "duplicate_ids": duplicate_ids},
        )
        approve_action = "workspace.entity.cluster_promoted"
        merge_result = {
            "status": "promoted",
            "entity_merge_item_id": merge_item["id"],
            "payload": payload,
        }
        scenario, reasoning_text, cluster_detail = build_entity_cluster_promote_decision(
            knowledge,
            workspace_id,
            review_item_id=item_id,
            primary_id=primary_id,
            duplicate_ids=duplicate_ids,
            cluster_payload=payload,
        )
        graph_decision_id = record_governance_decision_for_workspace(
            workspace_id,
            message=scenario,
            detail=cluster_detail,
            reasoning=reasoning_text,
            category="merge",
            outcome="deferred",
            actor_id=user.id,
            runtime_loader=lambda: deps.runtime_loader(),
            persist_graph=lambda kid: deps.persist_graph(kid),
        )
        decision_id = graph_decision_id
    elif item["kind"] == LOW_CONFIDENCE_KIND:
        payload = dict(item.get("payload") or {})
        statement_id = str(payload.get("statement_id") or item["subject_id"])
        resolution = resolve_low_confidence_approve(knowledge, workspace_id, statement_id)
        deps.rebuild_projection()
        approve_action = "workspace.statement.low_confidence_confirmed"
        merge_result = {"status": "confirmed", "resolution": resolution, "payload": payload}
    elif item["kind"] == SHACL_VIOLATION_KIND:
        payload = dict(item.get("payload") or {})
        approve_action = "workspace.shacl.violation_acknowledged"
        merge_result = {"status": "acknowledged", "payload": payload}
    elif item["kind"] == "connector_writeback":
        approve_action = "workspace.connector.writeback_approved"
        outbox_id = str((item.get("payload") or {}).get("outbox_id") or item["subject_id"])
        sync_svc = knowledge.connector_sync_service()
        executed_outbox = sync_svc.approve_and_execute_outbox(
            workspace_id,
            outbox_id,
            actor_id=user.id,
            rationale=rationale or "Approved connector writeback",
        )
        deps.rebuild_projection()
        decision_id = executed_outbox.get("decision_id")
        resolved_item = knowledge.get_review_item(workspace_id, item_id)
        audit_graph(
            store,
            user,
            workspace_id,
            approve_action,
            review_item_id=item_id,
            extra={
                "outbox_id": outbox_id,
                "decision_id": decision_id,
                "rationale": rationale,
            },
        )
        return {
            "item": resolved_item,
            "merge": None,
            "import": None,
            "mapping": None,
            "outbox": executed_outbox,
            "decision_id": decision_id,
        }
    elif item["kind"] == "graph_import":
        approve_action = "workspace.graph.import"
        runtime = deps.runtime_loader()
        session = require_graph_session(runtime)
        if deps.blob_store is None:
            raise AdminError(500, "internal_error", "blob store required for graph import approve")
        upload = upload_file_from_staged(deps.blob_store, workspace_id, item["payload"])
        raw_bytes = await upload.read()
        import_result = await asyncio.to_thread(
            import_graph_file,
            session,
            filename=str(upload.filename or "import.json"),
            content=raw_bytes,
        )
        deps.persist_graph(workspace_id)
        discard_staged_import(deps.blob_store, workspace_id, item["payload"])
    else:
        raise AdminError(422, "unsupported_review_kind", f"不支持的审核类型: {item['kind']}")

    if decision_id is None:
        decision_id = record_governance_decision_for_workspace(
            workspace_id,
            message=f"Review approve: {item['kind']}",
            detail={"item_id": item_id, "kind": item.get("kind")},
            actor_id=user.id,
            runtime_loader=lambda: deps.runtime_loader(),
            persist_graph=lambda kid: deps.persist_graph(kid),
        )

    resolved = knowledge.resolve_review_item(
        workspace_id,
        item_id,
        status="approved",
        resolved_by=user.id,
        rationale=rationale,
    )
    audit_extra: dict[str, Any] = {
        "merge": merge_result,
        "import": import_result,
        "rationale": rationale,
        **(
            {
                "ledger_notice": merge_result.get("ledger_notice"),
                "ledger_skipped_ids": merge_result.get("ledger_skipped_ids"),
            }
            if isinstance(merge_result, dict) and merge_result.get("ledger_notice")
            else {}
        ),
    }
    if decision_id:
        audit_extra["decision_id"] = decision_id
    audit_graph(
        store,
        user,
        workspace_id,
        approve_action,
        review_item_id=item_id,
        extra=audit_extra,
    )
    return {
        "item": resolved,
        "merge": merge_result,
        "import": import_result,
        "mapping": mapping_result,
        "decision_id": decision_id,
    }
