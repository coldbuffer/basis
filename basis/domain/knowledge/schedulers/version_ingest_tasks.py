"""Background version ingest with per-workspace graph locking."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import FastAPI

from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.knowledge.search import ChunkSearchService
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.domain.knowledge.pipeline.file_ingest import FileParseError
from basis.infra.runtime.observability.log_context import correlation_log_extra
from basis.infra.runtime.observability.request_context import reset_request_id, set_request_id
from basis.domain.knowledge.pipeline.extract_timeout import ExtractionTimeoutError
from basis.domain.knowledge.pipeline.version_ingest import (
    ExtractTextTooLargeError,
    TooManyChunksError,
    run_version_ingest,
)

_workspace_locks: dict[str, threading.Lock] = {}
_lock_guard = threading.Lock()

_ingest_inflight = 0
_ingest_idle = threading.Event()
_ingest_idle.set()


def wait_for_background_ingest(timeout: float = 120.0) -> None:
    """Block until fire-and-forget ingest worker threads finish (pytest pool teardown)."""
    _ingest_idle.wait(timeout=timeout)


def _ingest_worker_enter() -> None:
    global _ingest_inflight
    with _lock_guard:
        _ingest_inflight += 1
        if _ingest_inflight > 0:
            _ingest_idle.clear()


def _ingest_worker_exit() -> None:
    global _ingest_inflight
    with _lock_guard:
        _ingest_inflight -= 1
        if _ingest_inflight <= 0:
            _ingest_inflight = 0
            _ingest_idle.set()

_INGEST_OVERLOADED_MESSAGE = "处理队列已满，请稍后重试"


def _fail_ingest_overloaded(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
) -> None:
    knowledge: KnowledgeStore = app.state.knowledge_store
    knowledge.fail_version(
        workspace_id, version_id, "ingest_overloaded", _INGEST_OVERLOADED_MESSAGE
    )
    knowledge.fail_job(workspace_id, job_id, "ingest_overloaded", _INGEST_OVERLOADED_MESSAGE)


def _workspace_lock(workspace_id: str) -> threading.Lock:
    with _lock_guard:
        lock = _workspace_locks.get(workspace_id)
        if lock is None:
            lock = threading.Lock()
            _workspace_locks[workspace_id] = lock
        return lock


def run_version_ingest_for_app(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
    *,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions,
    trigger_request_id: str | None = None,
) -> dict[str, Any] | None:
    """Load graph, run ingest, persist. Returns result dict or None if parse failed."""
    bind_token = None
    if trigger_request_id and trigger_request_id.strip():
        bind_token = set_request_id(trigger_request_id.strip())
    try:
        return _run_version_ingest_for_app(
            app,
            workspace_id,
            version_id,
            job_id,
            filename=filename,
            graph_doc_id=graph_doc_id,
            options=options,
        )
    finally:
        if bind_token is not None:
            reset_request_id(bind_token)


def _run_version_ingest_for_app(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
    *,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions,
) -> dict[str, Any] | None:
    knowledge: KnowledgeStore = app.state.knowledge_store
    chunk_search: ChunkSearchService = app.state.chunk_search
    persistence: GraphPersistence = app.state.graph_persistence
    graphs: dict[str, Any] = app.state.graphs

    with _workspace_lock(workspace_id):
        session = graphs.get(workspace_id)
        if session is None:
            session = persistence.load(workspace_id)
            graphs[workspace_id] = session
        try:
            limits = app.state.limits
            endpoint_id = (options.llm_endpoint_id or "").strip()
            if endpoint_id:
                chat_llm = app.state.store.get_chat_llm_settings_for_entry(endpoint_id)
            else:
                chat_llm = app.state.store.get_chat_llm_settings()
            result = run_version_ingest(
                knowledge,
                session,
                workspace_id,
                version_id,
                job_id,
                filename=filename,
                graph_doc_id=graph_doc_id,
                options=options,
                chunk_search=chunk_search,
                max_extract_chars=limits.ingest_max_extract_chars,
                max_chunks=limits.ingest_max_chunks,
                extract_timeout_seconds=limits.ingest_extract_timeout_seconds,
                chat_llm=chat_llm,
            )
        except FileParseError:
            return None
        except (ExtractTextTooLargeError, TooManyChunksError):
            raise
        except ExtractionTimeoutError as exc:
            logger.warning(
                "version ingest extract timeout workspace_id=%s version_id=%s job_id=%s timeout_sec=%s",
                workspace_id,
                version_id,
                job_id,
                exc.timeout_seconds,
                extra=correlation_log_extra(
                    workspace_id=workspace_id,
                    version_id=version_id,
                    job_id=job_id,
                ),
            )
            raise
        except Exception:
            logger.exception(
                "version ingest failed workspace_id=%s version_id=%s job_id=%s",
                workspace_id,
                version_id,
                job_id,
                extra=correlation_log_extra(
                    workspace_id=workspace_id,
                    version_id=version_id,
                    job_id=job_id,
                ),
            )
            return None
        ledger = knowledge.get_projection_state(workspace_id)
        logger.info(
            "version ingest completed workspace_id=%s version_id=%s job_id=%s projection_revision=%s",
            workspace_id,
            version_id,
            job_id,
            ledger["revision"],
            extra=correlation_log_extra(
                workspace_id=workspace_id,
                version_id=version_id,
                job_id=job_id,
                projection_revision=ledger["revision"],
            ),
        )
        persistence.save(
            workspace_id,
            session,
            projection_revision=ledger["revision"],
            schema_version=ledger["schema_version"],
        )
        app.state.graph_session_registry.invalidate(workspace_id)
        app.state.ws_hub.try_broadcast(
            workspace_id,
            {
                "type": "projection_updated",
                "workspace_id": workspace_id,
                "projection_revision": ledger["revision"],
            },
        )
        return result


def enqueue_version_ingest(
    app: FastAPI,
    workspace_id: str,
    version_id: str,
    job_id: str,
    *,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions,
    trigger_request_id: str | None = None,
) -> None:
    """Fire-and-forget ingest on a worker thread (same process)."""

    pending_slot = getattr(app.state, "ingest_pending_slot", None)
    if pending_slot is not None and not pending_slot.acquire(blocking=False):
        _fail_ingest_overloaded(app, workspace_id, version_id, job_id)
        return

    def _work() -> None:
        _ingest_worker_enter()
        try:
            run_version_ingest_for_app(
                app,
                workspace_id,
                version_id,
                job_id,
                filename=filename,
                graph_doc_id=graph_doc_id,
                options=options,
                trigger_request_id=trigger_request_id,
            )
        finally:
            if pending_slot is not None:
                pending_slot.release()
            _ingest_worker_exit()

    if getattr(app.state.settings, "ingest_inline", False):
        _work()
        return
    executor = getattr(app.state, "ingest_executor", None)
    if executor is not None:
        executor.submit(_work)
        return
    threading.Thread(target=_work, name=f"ingest-{job_id[:8]}", daemon=True).start()
