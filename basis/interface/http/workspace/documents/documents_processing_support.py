"""Shared helpers for document processing jobs."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.responses import JSONResponse

from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore
from basis.domain.knowledge.ledger_rows import StoreDocumentOutcome
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.workspace.documents.ingest_helpers import ingest_accept_payload
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.interface.http.workspace.documents.documents_models import StartProcessingRequest


def document_store_payload(
    knowledge: KnowledgeStore,
    workspace_id: str,
    outcome: StoreDocumentOutcome,
    *,
    doc_id: str,
    filename: str,
) -> dict[str, Any]:
    version = knowledge.get_version(workspace_id, outcome.version_id)
    unchanged = not outcome.new_document and not outcome.new_version
    return {
        "document_id": outcome.document_id,
        "version_id": outcome.version_id,
        "doc_id": doc_id,
        "filename": filename,
        "version_no": outcome.version_no,
        "new_document": outcome.new_document,
        "new_version": outcome.new_version,
        "unchanged": unchanged,
        "status": version.status,
        "byte_size": outcome.blob.byte_size,
    }


async def await_terminal_processing_job(
    knowledge: KnowledgeStore,
    workspace_id: str,
    job_id: str,
    *,
    timeout_sec: float = 600,
) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout_sec
    while asyncio.get_running_loop().time() < deadline:
        job = knowledge.get_job(workspace_id, job_id)
        if job.status in {"succeeded", "failed", "cancelled"}:
            return job
        await asyncio.sleep(0.25)
    raise AdminError(504, "job_timeout", "处理任务等待超时")


async def respond_idempotent_processing_job(
    knowledge: KnowledgeStore,
    workspace_id: str,
    job: dict[str, Any],
    body: StartProcessingRequest,
    context: dict[str, Any],
    *,
    timeout_sec: float = 600,
) -> Any:
    if job["subject_id"] != body.version_id:
        raise AdminError(409, "idempotency_key_mismatch", "幂等键已用于其他文档版本")
    if job["status"] == "failed":
        raise AdminError(
            409,
            "idempotency_replay_failed",
            "幂等键对应任务已失败，请使用新幂等键重试",
        )
    if job["status"] == "cancelled":
        raise AdminError(409, "idempotency_replay_cancelled", "幂等键对应任务已取消")

    replay_meta = {"idempotent_replay": True, "job_id": job["id"]}

    if body.wait:
        terminal = (
            knowledge.get_job(workspace_id, job["id"])
            if job["status"] in {"succeeded", "failed", "cancelled"}
            else await await_terminal_processing_job(
                knowledge,
                workspace_id,
                job["id"],
                timeout_sec=timeout_sec,
            )
        )
        if terminal.status == "failed":
            raise AdminError(
                409,
                "idempotency_replay_failed",
                "幂等键对应任务已失败，请使用新幂等键重试",
            )
        if terminal.status == "cancelled":
            raise AdminError(409, "idempotency_replay_cancelled", "幂等键对应任务已取消")
        if terminal.result:
            return {
                **terminal.result,
                **replay_meta,
                "filename": context["filename"],
                "doc_id": context["doc_id"],
                "document_id": context["document_id"],
                "version_id": body.version_id,
            }
        return {**replay_meta, "status": terminal.status}

    if job["status"] == "succeeded" and job.get("result"):
        return {**job["result"], **replay_meta, "version_id": body.version_id}

    payload = ingest_accept_payload(
        job_id=job["id"],
        version_id=body.version_id,
        ledger_document_id=context["document_id"],
        doc_id=context["doc_id"],
        filename=context["filename"],
    )
    payload.update(replay_meta)
    payload["status"] = job["status"]
    status_code = 202 if job["status"] in {"queued", "running"} else 200
    return JSONResponse(status_code=status_code, content=payload)


def processing_options(
    body: StartProcessingRequest,
    store: AdminStore,
    *,
    filename: str | None = None,
) -> tuple[TextIngestOptions, dict[str, Any]]:
    from basis.domain.knowledge.pipeline.chunk_split import default_chunk_method, normalize_chunk_method

    if body.chunk and body.chunk_overlap >= body.chunk_size:
        raise AdminError(422, "bad_chunk_options", "切分重叠必须小于块大小")
    requested = (body.chunk_method or "").strip() or None
    try:
        chunk_method = (
            normalize_chunk_method(requested)
            if requested
            else default_chunk_method(filename)
        )
    except ValueError:
        raise AdminError(422, "bad_chunk_method", "切分方式无效") from None
    from basis.domain.knowledge.pipeline.extract_methods import (
        normalize_ner_method,
        normalize_relation_method,
    )

    extract = body.extract
    ner_method = normalize_ner_method(body.ner_method, extract=extract)
    relation_method = normalize_relation_method(body.relation_method, extract=extract)
    llm_model = (body.llm_model or "").strip() or None
    llm_endpoint_id = (body.llm_endpoint_id or "").strip() or None
    payload = {
        "chunk": body.chunk,
        "chunk_method": chunk_method,
        "chunk_size": body.chunk_size,
        "chunk_overlap": body.chunk_overlap,
        "extract": extract,
        "ner_method": ner_method,
        "relation_method": relation_method,
        "extract_relations": body.extract_relations,
        "ner_model": None,
        "llm_model": llm_model,
        "llm_endpoint_id": llm_endpoint_id,
    }
    options = TextIngestOptions(**payload)
    from basis.domain.knowledge.pipeline.extract_kwargs import validate_extract_options

    if llm_endpoint_id:
        chat_llm = store.get_chat_llm_settings_for_entry(llm_endpoint_id)
    else:
        chat_llm = store.get_chat_llm_settings()
    validate_extract_options(options, chat_llm)
    return options, payload
