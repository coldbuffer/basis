"""Chat/MCP remember → pending statement + review item (F-CHAT-04, ADR 0001)."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore

AGENT_REMEMBER_DOC_ID = "__basis_agent_remember__"
AGENT_REMEMBER_SUBJECT_LABEL = "Agent memory"
STATEMENT_REVIEW_KIND = "statement_remember"
STATEMENT_REVIEW_SUBJECT_TYPE = "statement"


def _agent_chunk(knowledge: KnowledgeStore, workspace_id: str, actor_id: str) -> str:
    doc = next(
        (d for d in knowledge.list_documents(workspace_id) if d.get("doc_id") == AGENT_REMEMBER_DOC_ID),
        None,
    )
    if doc is None:
        outcome = knowledge.store_document_bytes(
            workspace_id,
            title="Agent remembered facts",
            mime_type="text/plain",
            data=b"(synthetic anchor for chat/MCP remember proposals)\n",
            created_by=actor_id,
            external_key=AGENT_REMEMBER_DOC_ID,
        )
        version_id = outcome.version_id
        return knowledge.create_chunk(
            workspace_id,
            version_id,
            ordinal=0,
            text="Agent-proposed facts awaiting review are anchored here.",
        )
    version_id = doc.get("version_id")
    if not version_id:
        raise AdminError(500, "remember_anchor_broken", "Agent remember 锚点文档无版本")
    chunks = knowledge.list_chunks_for_version(workspace_id, version_id)
    if chunks:
        return chunks[0]["id"]
    return knowledge.create_chunk(
        workspace_id,
        version_id,
        ordinal=0,
        text="Agent-proposed facts awaiting review are anchored here.",
    )


def propose_remember(
    knowledge: KnowledgeStore,
    workspace_id: str,
    actor_id: str,
    content: str,
    *,
    source: str = "agent",
    chunk_id: str | None = None,
    quote: str | None = None,
) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise AdminError(422, "validation_error", "remember 内容不能为空")
    if len(text) > 8000:
        raise AdminError(422, "validation_error", "remember 内容过长")

    from basis.domain.knowledge.evidence import quote_from_chunk, resolve_workspace_chunk

    evidence_chunk_id: str
    if chunk_id and str(chunk_id).strip():
        row = resolve_workspace_chunk(knowledge, workspace_id, str(chunk_id))
        evidence_chunk_id = str(row.get("id") or chunk_id).strip()
        resolved_quote = quote_from_chunk(row, override=quote, fallback=text)
    else:
        evidence_chunk_id = _agent_chunk(knowledge, workspace_id, actor_id)
        resolved_quote = (quote or text).strip()
        if len(resolved_quote) > 512:
            resolved_quote = resolved_quote[:509] + "..."

    chunk_id = evidence_chunk_id
    subject_id = knowledge.get_or_create_entity_by_label(workspace_id, AGENT_REMEMBER_SUBJECT_LABEL)
    quote = resolved_quote

    statement_id = knowledge.add_open_statement(
        workspace_id,
        subject_id=subject_id,
        surface_phrase="remember",
        object_entity_id=None,
        object_value=text,
        status="pending",
        proposed_by=f"{source}:{actor_id}",
        chunk_id=chunk_id,
        quote=quote,
    )
    try:
        item = knowledge.create_review_item(
            workspace_id,
            kind=STATEMENT_REVIEW_KIND,
            subject_type=STATEMENT_REVIEW_SUBJECT_TYPE,
            subject_id=statement_id,
            payload={
                "statement_id": statement_id,
                "content": text,
                "source": source,
                "proposed_by": actor_id,
                "chunk_id": chunk_id,
            },
        )
    except AdminError as exc:
        if exc.code == "review_exists":
            knowledge.invalidate_statement(workspace_id, statement_id)
        raise
    return {
        "statement_id": statement_id,
        "review_item_id": item["id"],
        "status": "pending",
        "chunk_id": chunk_id,
        "quote": quote,
    }
