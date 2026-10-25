"""Knowledge application services."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import chunk_search_limit_max, require_workspace_editor
from basis.domain.errors import AdminError
from basis.domain.knowledge.services.remember_service import propose_remember


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
