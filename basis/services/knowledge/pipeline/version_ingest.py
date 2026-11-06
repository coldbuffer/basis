"""Ingest a stored document version: parse → chunk → graph extract (dual-write phase)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from basis.services.graph.projection.session import GraphSession
from basis.services.knowledge.search import ChunkSearchService
from basis.services.knowledge.store import KnowledgeStore
from basis.services.knowledge.pipeline.chunk_meta import prepare_chunks
from basis.services.knowledge.pipeline.document import TextIngestOptions, build_kg_from_text
from basis.services.knowledge.pipeline.extract_timeout import ExtractionTimeoutError
from basis.services.knowledge.pipeline.file_ingest import FileParseError, text_from_bytes
from basis.services.graph.projection.projector import apply_rebuild_to_session
from basis.services.knowledge.pipeline.ledger_extract import apply_kg_to_ledger
from basis.services.knowledge.pipeline.ingest_control import (
    clear_ingest_pause,
    ingest_pause_requested,
    mark_version_paused,
)


class ExtractTextTooLargeError(Exception):
    def __init__(self, char_count: int, max_chars: int) -> None:
        self.char_count = char_count
        self.max_chars = max_chars
        self.message = f"提取文本超过 {max_chars} 字符限制"
        super().__init__(self.message)


class TooManyChunksError(Exception):
    def __init__(self, chunk_count: int, max_chunks: int) -> None:
        self.chunk_count = chunk_count
        self.max_chunks = max_chunks
        self.message = f"切分块数超过 {max_chunks} 限制"
        super().__init__(self.message)


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized parser output for a single uploaded file."""

    full_text: str
    filename: str


def parse_uploaded_bytes(filename: str, data: bytes) -> ParsedDocument:
    text = text_from_bytes(filename, data)
    return ParsedDocument(full_text=text, filename=filename)


@dataclass
class _IngestProgress:
    completed_chunk_ids: list[str]
    chunk_count: int
    embed_done: bool
    ledger_entities_written: int
    ledger_statements_written: int
    ledger_drops_recorded: int

    def completed_set(self) -> set[str]:
        return set(self.completed_chunk_ids)

    def as_checkpoint(self) -> dict[str, Any]:
        return {
            "completed_chunk_ids": list(self.completed_chunk_ids),
            "chunk_count": self.chunk_count,
            "embed_done": self.embed_done,
            "ledger_entities_written": self.ledger_entities_written,
            "ledger_statements_written": self.ledger_statements_written,
            "ledger_drops_recorded": self.ledger_drops_recorded,
        }

    def progress_value(self) -> float:
        if self.chunk_count <= 0:
            return 0.0
        return min(1.0, len(self.completed_chunk_ids) / self.chunk_count)

    def note_chunk(self, chunk_id: str, part_stats: dict[str, Any]) -> None:
        if chunk_id not in self.completed_set():
            self.completed_chunk_ids.append(chunk_id)
        self.ledger_entities_written += int(part_stats.get("ledger_entities_written") or 0)
        self.ledger_statements_written += int(part_stats.get("ledger_statements_written") or 0)
        self.ledger_drops_recorded += int(part_stats.get("ledger_drops_recorded") or 0)


def _progress_from_job(knowledge: KnowledgeStore, workspace_id: str, job_id: str) -> _IngestProgress:
    job = knowledge.get_job(workspace_id, job_id)
    raw = job.result.get("checkpoint") if isinstance(job.result, dict) else None
    if not isinstance(raw, dict):
        raw = {}
    completed: list[str] = []
    seen: set[str] = set()
    for item in raw.get("completed_chunk_ids") or []:
        chunk_id = str(item)
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            completed.append(chunk_id)
    return _IngestProgress(
        completed_chunk_ids=completed,
        chunk_count=int(raw.get("chunk_count") or 0),
        embed_done=bool(raw.get("embed_done")),
        ledger_entities_written=int(raw.get("ledger_entities_written") or 0),
        ledger_statements_written=int(raw.get("ledger_statements_written") or 0),
        ledger_drops_recorded=int(raw.get("ledger_drops_recorded") or 0),
    )


def _persist_progress(
    knowledge: KnowledgeStore,
    workspace_id: str,
    job_id: str,
    progress: _IngestProgress,
) -> None:
    knowledge.set_job_checkpoint(
        workspace_id,
        job_id,
        progress.as_checkpoint(),
        progress.progress_value(),
    )


def _paused_payload(
    *,
    job_id: str,
    version_id: str,
    graph_doc_id: str,
    progress: _IngestProgress,
) -> dict[str, Any]:
    clear_ingest_pause(job_id)
    return {
        "status": "paused",
        "job_id": job_id,
        "version_id": version_id,
        "document_id": graph_doc_id,
        "chunk_count": progress.chunk_count,
        "checkpoint": progress.as_checkpoint(),
    }


def _pause_job(
    knowledge: KnowledgeStore,
    workspace_id: str,
    version_id: str,
    job_id: str,
    graph_doc_id: str,
    progress: _IngestProgress,
) -> dict[str, Any]:
    _persist_progress(knowledge, workspace_id, job_id, progress)
    knowledge.try_transition_job_status(
        workspace_id,
        job_id,
        "paused",
        expect={"queued", "running"},
    )
    mark_version_paused(knowledge, workspace_id, version_id)
    return _paused_payload(
        job_id=job_id,
        version_id=version_id,
        graph_doc_id=graph_doc_id,
        progress=progress,
    )


def run_version_ingest(
    knowledge: KnowledgeStore,
    graph: GraphSession,
    workspace_id: str,
    version_id: str,
    job_id: str,
    *,
    filename: str,
    graph_doc_id: str,
    options: TextIngestOptions | None = None,
    chunk_search: ChunkSearchService | None = None,
    max_extract_chars: int | None = None,
    max_chunks: int | None = None,
    extract_timeout_seconds: float | None = None,
    chat_llm: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Run the ingest pipeline for one version. Updates job/version status in the ledger."""
    options = options or TextIngestOptions(chunk=True)
    progress = _progress_from_job(knowledge, workspace_id, job_id)

    def paused_now() -> dict[str, Any] | None:
        if not ingest_pause_requested(job_id):
            return None
        return _pause_job(
            knowledge, workspace_id, version_id, job_id, graph_doc_id, progress
        )

    if ingest_pause_requested(job_id):
        return _pause_job(knowledge, workspace_id, version_id, job_id, graph_doc_id, progress)
    current = knowledge.get_job(workspace_id, job_id)
    if current.status == "paused":
        return _paused_payload(
            job_id=job_id,
            version_id=version_id,
            graph_doc_id=graph_doc_id,
            progress=progress,
        )
    if current.status != "queued":
        return {
            "status": current.status,
            "job_id": job_id,
            "version_id": version_id,
            "document_id": graph_doc_id,
        }
    if not knowledge.try_transition_job_status(
        workspace_id, job_id, "running", expect={"queued"}
    ):
        current = knowledge.get_job(workspace_id, job_id)
        if current.status == "paused":
            return _paused_payload(
                job_id=job_id,
                version_id=version_id,
                graph_doc_id=graph_doc_id,
                progress=progress,
            )
        return {
            "status": current.status,
            "job_id": job_id,
            "version_id": version_id,
            "document_id": graph_doc_id,
        }
    early = paused_now()
    if early is not None:
        return early

    def fail(code: str, message: str) -> None:
        clear_ingest_pause(job_id)
        knowledge.fail_version(workspace_id, version_id, code, message)
        knowledge.fail_job(workspace_id, job_id, code, message)

    try:
        existing_chunks = knowledge.list_chunks_for_version(workspace_id, version_id)
        reuse_chunks = bool(existing_chunks) and (
            bool(progress.completed_chunk_ids) or progress.embed_done or progress.chunk_count > 0
        )
        if reuse_chunks:
            chunk_rows = existing_chunks
            chunk_texts = [row["text"] for row in chunk_rows]
        else:
            knowledge.set_version_status(workspace_id, version_id, "parsing")
            early = paused_now()
            if early is not None:
                return early
            raw = knowledge.read_version_bytes(workspace_id, version_id)
            parsed = parse_uploaded_bytes(filename, raw)
            if max_extract_chars is not None and max_extract_chars > 0:
                char_count = len(parsed.full_text)
                if char_count > max_extract_chars:
                    raise ExtractTextTooLargeError(char_count, max_extract_chars)
            knowledge.set_version_status(workspace_id, version_id, "chunking")
            early = paused_now()
            if early is not None:
                return early

            chunk_payloads = prepare_chunks(parsed.full_text, options)
            chunk_texts = [
                row if isinstance(row, str) else row["text"] for row in chunk_payloads
            ]
            if not chunk_texts and parsed.full_text.strip():
                chunk_texts = [parsed.full_text]
            if max_chunks is not None and max_chunks > 0 and len(chunk_texts) > max_chunks:
                raise TooManyChunksError(len(chunk_texts), max_chunks)

            if existing_chunks:
                existing_texts = [row["text"] for row in existing_chunks]
                if existing_texts != chunk_texts:
                    raise ValueError(
                        "version_already_chunked: create a new document version to change chunk options"
                    )
            else:
                knowledge.create_chunks(workspace_id, version_id, chunk_payloads)
            chunk_rows = knowledge.list_chunks_for_version(workspace_id, version_id)
            chunk_texts = [row["text"] for row in chunk_rows]

        progress.chunk_count = len(chunk_texts)
        _persist_progress(knowledge, workspace_id, job_id, progress)
        early = paused_now()
        if early is not None:
            return early

        embed_stats: dict[str, int] = {"indexed": 0, "skipped": 0}
        if not progress.embed_done:
            search_config = knowledge.get_search_config(workspace_id)
            if (
                chunk_search is not None
                and chunk_texts
                and search_config.semantic_enabled
                and search_config.auto_index
            ):
                knowledge.set_version_status(workspace_id, version_id, "embedding")
                early = paused_now()
                if early is not None:
                    return early
                embed_stats = chunk_search.index_version(workspace_id, version_id)
            progress.embed_done = True
            _persist_progress(knowledge, workspace_id, job_id, progress)
        early = paused_now()
        if early is not None:
            return early

        knowledge.set_version_status(workspace_id, version_id, "extracting")
        has_text = any((row.get("text") or "").strip() for row in chunk_rows)
        proposed_by = f"extract:{options.ner_method}:{options.relation_method}"
        if options.extract and has_text:
            for row in chunk_rows:
                early = paused_now()
                if early is not None:
                    return early
                if row["id"] in progress.completed_set():
                    continue
                chunk_doc_id = (
                    graph_doc_id
                    if len(chunk_rows) == 1
                    else f"{graph_doc_id}::chunk_{row['ordinal']}"
                )
                part = build_kg_from_text(
                    chunk_doc_id,
                    row["text"],
                    options,
                    chat_llm=chat_llm,
                    extract_timeout_seconds=extract_timeout_seconds,
                )
                part_stats = apply_kg_to_ledger(
                    knowledge,
                    workspace_id,
                    version_id,
                    row["id"],
                    row["text"],
                    part,
                    proposed_by=proposed_by,
                    statement_status="pending",
                )
                progress.note_chunk(str(row["id"]), part_stats)
                _persist_progress(knowledge, workspace_id, job_id, progress)
        early = paused_now()
        if early is not None:
            return early

        ledger_stats = {
            "ledger_entities_written": progress.ledger_entities_written,
            "ledger_statements_written": progress.ledger_statements_written,
            "ledger_drops_recorded": progress.ledger_drops_recorded,
        }
        shacl_scan: dict[str, Any] | None = None
        if ledger_stats["ledger_statements_written"] > 0:
            from basis.services.knowledge.conflict import run_shacl_conflict_scan

            shacl_scan = run_shacl_conflict_scan(knowledge, workspace_id)

        projection_meta = apply_rebuild_to_session(
            knowledge, workspace_id, graph, include_version_ids=(version_id,)
        )
        knowledge.set_version_status(workspace_id, version_id, "ready")

        graph_result: dict[str, Any] = {
            **projection_meta,
            "doc_id": graph_doc_id,
            "extracted": bool(options.extract and has_text),
            **ledger_stats,
        }
        if shacl_scan is not None:
            graph_result["shacl_scan"] = shacl_scan

        result = {
            **graph_result,
            "version_id": version_id,
            "job_id": job_id,
            "document_id": graph_doc_id,
            "chunk_count": len(chunk_texts),
            "embed_indexed": embed_stats.get("indexed", 0),
            "embed_skipped": embed_stats.get("skipped", 0),
            "ledger_status": "ready",
            "ledger_statement_count": knowledge.count_statements_for_version(workspace_id, version_id),
        }
        clear_ingest_pause(job_id)
        knowledge.set_job_result(workspace_id, job_id, result)
        knowledge.set_job_status(workspace_id, job_id, "succeeded")
        return result
    except FileParseError as exc:
        fail("parse_failed", exc.message)
        raise
    except ExtractTextTooLargeError as exc:
        fail("extract_text_too_large", exc.message)
        raise
    except TooManyChunksError as exc:
        fail("too_many_chunks", exc.message)
        raise
    except ExtractionTimeoutError as exc:
        fail("extract_timeout", exc.message)
        raise
    except Exception as exc:
        message = str(exc) or "ingest_failed"
        fail("ingest_failed", message)
        projection = knowledge.get_projection_state(workspace_id)
        if projection["status"] != "failed":
            knowledge.set_projection_status(workspace_id, "dirty", error_code="ingest_incomplete")
        raise
