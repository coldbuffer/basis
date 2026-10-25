"""Ingest a stored document version: parse → chunk → graph extract (dual-write phase)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.search import ChunkSearchService
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.knowledge.pipeline.chunk_meta import prepare_chunks
from basis.domain.knowledge.pipeline.document import TextIngestOptions, _normalize_text, build_kg_from_text
from basis.domain.knowledge.pipeline.extract_timeout import ExtractionTimeoutError
from basis.domain.knowledge.pipeline.file_ingest import FileParseError, text_from_bytes
from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.knowledge.pipeline.ledger_extract import apply_kg_to_ledger


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
    knowledge.set_job_status(workspace_id, job_id, "running")
    knowledge.set_version_status(workspace_id, version_id, "parsing")

    try:
        raw = knowledge.read_version_bytes(workspace_id, version_id)
        parsed = parse_uploaded_bytes(filename, raw)
        if max_extract_chars is not None and max_extract_chars > 0:
            char_count = len(parsed.full_text)
            if char_count > max_extract_chars:
                raise ExtractTextTooLargeError(char_count, max_extract_chars)
        knowledge.set_version_status(workspace_id, version_id, "chunking")

        chunk_payloads = prepare_chunks(parsed.full_text, options)
        chunk_texts = [
            row if isinstance(row, str) else row["text"] for row in chunk_payloads
        ]
        if not chunk_texts and parsed.full_text.strip():
            chunk_texts = [parsed.full_text]
        if max_chunks is not None and max_chunks > 0 and len(chunk_texts) > max_chunks:
            raise TooManyChunksError(len(chunk_texts), max_chunks)

        existing_chunks = knowledge.list_chunks_for_version(workspace_id, version_id)
        if existing_chunks:
            existing_texts = [row["text"] for row in existing_chunks]
            if existing_texts != chunk_texts:
                raise ValueError(
                    "version_already_chunked: create a new document version to change chunk options"
                )
        else:
            knowledge.create_chunks(workspace_id, version_id, chunk_payloads)

        embed_stats: dict[str, int] = {"indexed": 0, "skipped": 0}
        search_config = knowledge.get_search_config(workspace_id)
        if (
            chunk_search is not None
            and chunk_texts
            and search_config.semantic_enabled
            and search_config.auto_index
        ):
            knowledge.set_version_status(workspace_id, version_id, "embedding")
            embed_stats = chunk_search.index_version(workspace_id, version_id)

        knowledge.set_version_status(workspace_id, version_id, "extracting")
        chunk_rows = knowledge.list_chunks_for_version(workspace_id, version_id)
        normalized = _normalize_text(parsed.full_text)
        ledger_stats = {
            "ledger_entities_written": 0,
            "ledger_statements_written": 0,
            "ledger_drops_recorded": 0,
        }
        proposed_by = f"extract:{options.ner_method}:{options.relation_method}"

        if options.extract and normalized.strip():
            for row in chunk_rows:
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
                for key in ledger_stats:
                    ledger_stats[key] += part_stats.get(key, 0)

        shacl_scan: dict[str, Any] | None = None
        if ledger_stats["ledger_statements_written"] > 0:
            from basis.domain.knowledge.services.conflict_review import run_shacl_conflict_scan

            shacl_scan = run_shacl_conflict_scan(knowledge, workspace_id)

        projection_meta = apply_rebuild_to_session(
            knowledge, workspace_id, graph, include_version_ids=(version_id,)
        )
        knowledge.set_version_status(workspace_id, version_id, "ready")

        graph_result: dict[str, Any] = {
            **projection_meta,
            "doc_id": graph_doc_id,
            "extracted": bool(options.extract and normalized.strip()),
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
        knowledge.set_job_result(workspace_id, job_id, result)
        knowledge.set_job_status(workspace_id, job_id, "succeeded")
        return result
    except FileParseError as exc:
        knowledge.fail_version(workspace_id, version_id, "parse_failed", exc.message)
        knowledge.fail_job(workspace_id, job_id, "parse_failed", exc.message)
        raise
    except ExtractTextTooLargeError as exc:
        knowledge.fail_version(workspace_id, version_id, "extract_text_too_large", exc.message)
        knowledge.fail_job(workspace_id, job_id, "extract_text_too_large", exc.message)
        raise
    except TooManyChunksError as exc:
        knowledge.fail_version(workspace_id, version_id, "too_many_chunks", exc.message)
        knowledge.fail_job(workspace_id, job_id, "too_many_chunks", exc.message)
        raise
    except ExtractionTimeoutError as exc:
        knowledge.fail_version(workspace_id, version_id, "extract_timeout", exc.message)
        knowledge.fail_job(workspace_id, job_id, "extract_timeout", exc.message)
        raise
    except Exception as exc:
        message = str(exc) or "ingest_failed"
        knowledge.fail_version(workspace_id, version_id, "ingest_failed", message)
        knowledge.fail_job(workspace_id, job_id, "ingest_failed", message)
        projection = knowledge.get_projection_state(workspace_id)
        if projection["status"] != "failed":
            knowledge.set_projection_status(workspace_id, "dirty", error_code="ingest_incomplete")
        raise
