"""Knowledge application services."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import chunk_search_limit_max, require_workspace_editor
from basis.domain.errors import AdminError
from basis.domain.knowledge.services.remember_service import propose_remember
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.services.entity_type_assign import (
    assign_entity_type,
    assign_entity_types_batch,
    clear_entity_types_batch,
)
from basis.domain.knowledge.services.entity_invalidate import invalidate_entities_batch
from basis.domain.ontology.mappings.service import (
    apply_mapping_status_change,
    ensure_mapping_review_item,
)


def op_search_chunks(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query is required"}
    limit_max = chunk_search_limit_max(ctx, args)
    limit = min(max(1, int(args.get("limit", 10))), limit_max)
    document_id = str(args.get("document_id") or "").strip() or None
    entity_id = str(args.get("entity_id") or "").strip() or None
    as_of = str(args.get("as_of") or "").strip() or None
    created_after = str(args.get("created_after") or "").strip() or None
    created_before = str(args.get("created_before") or "").strip() or None
    mode = args.get("mode")
    if as_of and not created_before:
        created_before = as_of
    if ctx.chunk_search is not None:
        return ctx.chunk_search.search(
            ctx.workspace.id,
            query=query,
            limit=limit,
            document_id=document_id,
            entity_id=entity_id,
            created_after=created_after,
            created_before=created_before,
            as_of=as_of,
            mode=mode,
        )
    hits = ctx.knowledge.search_chunks(ctx.workspace.id, query=query, limit=limit)
    return {"query": query, "mode": "keyword", "chunks": hits}


def op_get_chunk(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    chunk_id = str(args.get("chunk_id", "")).strip()
    if not chunk_id:
        return {"error": "chunk_id is required"}
    row = ctx.knowledge.get_chunk(ctx.workspace.id, chunk_id)
    if row is None:
        return {"error": "chunk not found"}
    return {"chunk": row}


def op_propose_remember(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    content = str(args.get("content", "")).strip()
    if not content:
        return {"error": "content is required"}
    require_workspace_editor(ctx)
    source = str(args.get("source") or "mcp")
    chunk_id = str(args.get("chunk_id") or "").strip() or None
    quote_raw = args.get("quote")
    quote = str(quote_raw).strip() if quote_raw is not None else None
    try:
        payload = propose_remember(
            ctx.knowledge,
            ctx.workspace.id,
            ctx.user.id,
            content,
            source=source,
            chunk_id=chunk_id,
            quote=quote,
        )
    except AdminError as exc:
        return {"error": exc.code, "message": exc.message}
    return {
        **payload,
        "message": "Fact submitted for review; it is not searchable until approved.",
    }


def op_entity_facts(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(args.get("entity_id", "")).strip()
    if not entity_id:
        return {"error": "entity_id is required"}
    limit = int(args.get("limit", 50))
    wid = ctx.workspace.id
    facts = ctx.knowledge.list_entity_facts(wid, entity_id=entity_id, limit=limit)
    derived_facts = ctx.knowledge.list_derived_facts_for_entity(wid, entity_id, limit=limit)
    return {"entity_id": entity_id, "facts": facts, "derived_facts": derived_facts}


def op_list_derived_facts(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip() or None
    limit = min(max(1, int(args.get("limit", 100))), 200)
    wid = ctx.workspace.id
    if entity_id:
        derived_facts = ctx.knowledge.list_derived_facts_for_entity(wid, entity_id, limit=limit)
    else:
        derived_facts = ctx.knowledge.list_derived_facts(wid, limit=limit)
    return {"entity_id": entity_id, "derived_facts": derived_facts}


def op_list_typed_facts(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(1, int(args.get("limit", 100))), 200)
    facts = ctx.knowledge.list_typed_facts(ctx.workspace.id, limit=limit)
    return {"facts": facts}


def op_list_mappings(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    status = str(args.get("status") or "").strip() or None
    limit = min(max(1, int(args.get("limit", 100))), 200)
    mappings = ctx.knowledge.list_mappings(ctx.workspace.id, status=status, limit=limit)
    return {"mappings": mappings}


def op_get_statement(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    statement_id = str(args.get("statement_id", "")).strip()
    if not statement_id:
        return {"error": "statement_id is required"}
    summary = ctx.knowledge.get_statement_browse(ctx.workspace.id, statement_id=statement_id)
    if summary is None:
        return {"error": "statement not found"}
    return {"statement": summary}


def op_list_surface_phrases(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(1, int(args.get("limit", 100))), 200)
    phrases = ctx.knowledge.list_distinct_surface_phrases(ctx.workspace.id, limit=limit)
    return {"phrases": phrases}


def op_list_entity_type_object_labels(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(1, int(args.get("limit", 100))), 200)
    wid = ctx.workspace.id
    labels = ctx.knowledge.list_entity_type_object_labels(wid, limit=limit)
    return {
        "labels": labels,
        "type_surface_phrases": ctx.knowledge.entity_type_surface_phrases(wid),
    }


def op_assign_entity_types(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    raw = args.get("assignments")
    if not isinstance(raw, list) or not raw:
        return {"error": "assignments (non-empty array) is required"}
    replace_existing = bool(args.get("replace_existing", True))
    wid = ctx.workspace.id
    result = assign_entity_types_batch(
        ctx.knowledge,
        wid,
        raw,
        replace_existing=replace_existing,
    )
    projection = None
    if result.get("created", 0) > 0 and ctx.rebuild_projection is not None:
        projection = ctx.rebuild_projection()
    return {**result, "projection": projection}


def op_invalidate_entities(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    raw = args.get("entity_ids")
    if not isinstance(raw, list) or not raw:
        return {"error": "entity_ids (non-empty array) is required"}
    wid = ctx.workspace.id
    try:
        result = invalidate_entities_batch(ctx.knowledge, wid, [str(e) for e in raw])
    except AdminError as exc:
        return {"error": exc.code, "message": exc.message}
    projection = None
    if result.get("invalidated", 0) > 0 and ctx.rebuild_projection is not None:
        projection = ctx.rebuild_projection()
    return {**result, "projection": projection}


def op_delete_entity(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    entity_id = str(args.get("entity_id") or "").strip()
    if not entity_id:
        return {"error": "entity_id is required"}
    wid = ctx.workspace.id
    try:
        outcome = ctx.knowledge.delete_entity(wid, entity_id)
    except AdminError as exc:
        return {"error": exc.code, "message": exc.message}
    projection = None
    if ctx.rebuild_projection is not None:
        projection = ctx.rebuild_projection()
    return {"ok": True, **outcome, "projection": projection}


def op_delete_document(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    doc_ref = str(args.get("document_id") or args.get("doc_id") or "").strip()
    if not doc_ref:
        return {"error": "document_id is required"}
    wid = ctx.workspace.id
    context = ctx.knowledge.resolve_document_ref(wid, doc_ref)
    if context is None:
        return {"error": "not_found", "message": "文档不存在"}
    try:
        outcome = ctx.knowledge.hard_delete_document(wid, context["document_id"])
    except AdminError as exc:
        return {"error": exc.code, "message": exc.message}
    chunk_ids = outcome.get("chunk_ids") or []
    if chunk_ids and ctx.chunk_search is not None:
        ctx.chunk_search.delete_chunk_vectors(wid, chunk_ids)
    projection = None
    if ctx.rebuild_projection is not None:
        projection = ctx.rebuild_projection()
    return {"ok": True, **outcome, "projection": projection}


def op_clear_entity_types(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    raw = args.get("subject_ids")
    if not isinstance(raw, list) or not raw:
        return {"error": "subject_ids (non-empty array) is required"}
    wid = ctx.workspace.id
    result = clear_entity_types_batch(ctx.knowledge, wid, [str(s) for s in raw])
    projection = None
    if result.get("invalidated", 0) > 0 and ctx.rebuild_projection is not None:
        projection = ctx.rebuild_projection()
    return {**result, "projection": projection}


def op_propose_mapping(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    subject_id = str(args.get("subject_id") or "").strip()
    target_uri = str(args.get("target_uri") or "").strip() or None
    target_kind = str(args.get("target_kind") or "property").strip()
    if subject_id and target_kind == "class" and target_uri:
        require_workspace_editor(ctx)
        wid = ctx.workspace.id
        assignment = assign_entity_type(
            ctx.knowledge,
            wid,
            subject_id=subject_id,
            class_uri=target_uri,
        )
        projection = None
        if assignment.get("created", 0) > 0 and ctx.rebuild_projection is not None:
            projection = ctx.rebuild_projection()
        return {"assignment": assignment, "projection": projection}

    signature = str(args.get("signature", "")).strip()
    if not signature:
        return {"error": "signature is required (or subject_id + target_kind class + target_uri)"}
    status = str(args.get("status") or "proposed").strip()
    if status == "confirmed":
        require_workspace_editor(ctx)
    direction = str(args.get("direction") or "forward").strip()
    why = str(args.get("why") or "").strip() or None
    wid = ctx.workspace.id
    mapping = ctx.knowledge.create_mapping(
        wid,
        ctx.user.id,
        signature=signature,
        target_uri=target_uri,
        target_kind=target_kind,
        direction=direction,
        status=status,
        why=why,
    )
    materialized = None
    projection = None
    if status == "proposed":
        ensure_mapping_review_item(ctx.knowledge, wid, mapping)
    else:
        materialized = ctx.knowledge.materialize_mapping_facts(wid, mapping["id"])
        if materialized.get("created", 0) > 0 and ctx.rebuild_projection is not None:
            projection = ctx.rebuild_projection()
        from basis.domain.knowledge.services.governor_unmapped_types import (
            maybe_resolve_unmapped_entity_type_for_mapping,
        )

        maybe_resolve_unmapped_entity_type_for_mapping(
            ctx.knowledge,
            wid,
            mapping,
            resolved_by=ctx.user.id,
            rationale=why,
        )
    audit_graph(
        ctx.store,
        ctx.user,
        wid,
        "workspace.mapping.created",
        extra={
            "mapping_id": mapping["id"],
            "signature": mapping["signature"],
            "status": mapping["status"],
            "materialized": materialized,
        },
    )
    return {"mapping": mapping, "materialized": materialized, "projection": projection}


def op_update_mapping_status(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    mapping_id = str(args.get("mapping_id", "")).strip()
    if not mapping_id:
        return {"error": "mapping_id is required"}
    status = str(args.get("status", "")).strip()
    if status not in {"confirmed", "rejected", "superseded"}:
        return {"error": "status must be confirmed, rejected, or superseded"}
    why = str(args.get("why") or "").strip() or None
    return apply_mapping_status_change(
        ctx.workspace.id,
        mapping_id,
        ctx.user,
        ctx.store,
        ctx.knowledge,
        status=status,  # type: ignore[arg-type]
        why=why,
        sync_review=True,
        projection_bindings=ctx.projection_bindings,
    )
