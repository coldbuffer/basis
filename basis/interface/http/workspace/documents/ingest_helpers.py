"""Shared ingest request/response helpers for workspace document routes."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from basis.domain.knowledge.pipeline.accept_payload import ingest_accept_payload
from basis.domain.knowledge.schedulers.version_ingest_tasks import (
    enqueue_version_ingest,
    run_version_ingest_for_app,
)
from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.domain.knowledge.pipeline.file_ingest import FileParseError
from basis.domain.knowledge.pipeline.version_ingest import run_version_ingest


def run_ingest_blocking(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
    *,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions,
    graph_session: GraphSession | None = None,
    trigger_request_id: str | None = None,
) -> dict[str, Any]:
    knowledge: KnowledgeStore = app.state.knowledge_store
    limits = app.state.limits
    if graph_session is not None:
        endpoint_id = (options.llm_endpoint_id or "").strip()
        if endpoint_id:
            chat_llm = app.state.store.get_chat_llm_settings_for_entry(endpoint_id)
        else:
            chat_llm = app.state.store.get_chat_llm_settings()
        return run_version_ingest(
            knowledge,
            graph_session,
            workspace_id,
            version_id,
            job_id,
            filename=filename,
            graph_doc_id=graph_doc_id,
            options=options,
            chunk_search=app.state.chunk_search,
            max_extract_chars=limits.ingest_max_extract_chars,
            max_chunks=limits.ingest_max_chunks,
            extract_timeout_seconds=limits.ingest_extract_timeout_seconds,
            chat_llm=chat_llm,
        )
    result = run_version_ingest_for_app(
        app,
        workspace_id,
        version_id,
        job_id,
        filename=filename,
        graph_doc_id=graph_doc_id,
        options=options,
        trigger_request_id=trigger_request_id,
    )
    if result is None:
        raise FileParseError("parse_failed")
    return result


def respond_ingest(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
    ledger_document_id: str,
    *,
    wait: bool,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions,
    graph_session: GraphSession | None = None,
    trigger_request_id: str | None = None,
) -> JSONResponse | dict[str, Any]:
    if not wait:
        enqueue_version_ingest(
            app,
            workspace_id,
            version_id,
            job_id,
            filename=filename,
            graph_doc_id=graph_doc_id,
            options=options,
            trigger_request_id=trigger_request_id,
        )
        return JSONResponse(
            status_code=202,
            content=ingest_accept_payload(
                job_id=job_id,
                version_id=version_id,
                ledger_document_id=ledger_document_id,
                doc_id=graph_doc_id,
                filename=filename,
            ),
        )
    result = run_ingest_blocking(
        app,
        workspace_id,
        version_id,
        job_id,
        filename=filename,
        graph_doc_id=graph_doc_id,
        options=options,
        graph_session=graph_session,
        trigger_request_id=trigger_request_id,
    )
    return {
        **result,
        "filename": filename,
        "doc_id": graph_doc_id,
        "document_id": ledger_document_id,
        "version_id": version_id,
        "job_id": job_id,
    }
