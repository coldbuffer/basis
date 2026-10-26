"""Workspace retrieval orchestration over canonical chunks and pluggable vector indexes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.ports.platform import EmbedSettingsStore
from basis.domain.knowledge.search.embeddings import content_sha256, embed_query, embed_texts
from basis.domain.knowledge.search.search_config import SearchMode
from basis.domain.knowledge.search.vector_index import PgVectorIndex, SQLiteVectorIndex, VectorIndexBackend
from basis.domain.knowledge.store import KnowledgeStore

_RRF_K = 60


def _rrf_merge(
    ranked_ids: list[list[str]], limit: int
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranks in ranked_ids:
        for rank, chunk_id in enumerate(ranks):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ordered[:limit]


class ChunkSearchService:
    def __init__(
        self,
        knowledge: KnowledgeStore,
        admin: EmbedSettingsStore,
        data_dir: Path,
    ) -> None:
        self._knowledge = knowledge
        self._admin = admin
        self._backends: dict[str, VectorIndexBackend] = {
            "sqlite_vec": SQLiteVectorIndex(data_dir)
        }
        database = knowledge.database
        if database.backend == "postgres":
            self._backends["pgvector"] = PgVectorIndex(getattr(database, "engine"))

    def delete_chunk_vectors(self, workspace_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        self._backend(workspace_id).delete(workspace_id, chunk_ids)

    def _backend(self, workspace_id: str) -> VectorIndexBackend:
        name = self._knowledge.get_search_config(workspace_id).vector_backend
        backend = self._backends.get(name)
        if backend is None:
            raise AdminError(503, "vector_backend_unavailable", "向量存储后端不可用")
        return backend

    def _embed_settings(self, workspace_id: str) -> dict[str, str | None]:
        config = self._knowledge.get_search_config(workspace_id)
        return self._admin.get_embed_settings(config.embedding_model_id)

    def _current_model_ref(self, workspace_id: str) -> str:
        settings = self._embed_settings(workspace_id)
        api_key = (settings.get("api_key") or "").strip()
        model = (settings.get("model") or "").strip()
        if api_key and model:
            return f"openai-compat:{settings.get('id') or model}"
        return "semantica:fallback"

    def _chunk_filter_ids(
        self,
        workspace_id: str,
        *,
        document_id: str | None,
        entity_id: str | None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> set[str] | None:
        if not document_id and not entity_id and not created_after and not created_before:
            return None
        return self._knowledge.chunk_ids_matching_filters(
            workspace_id,
            document_id=document_id,
            entity_id=entity_id,
            created_after=created_after,
            created_before=created_before,
        )

    def index_chunks(self, workspace_id: str, chunk_ids: list[str] | None = None) -> dict[str, Any]:
        config = self._knowledge.get_search_config(workspace_id)
        if not config.semantic_enabled:
            return {"indexed": 0, "skipped": 0, "disabled": True}
        model_ref = self._current_model_ref(workspace_id)
        settings = self._embed_settings(workspace_id)
        rows = self._knowledge.list_chunks_for_indexing(workspace_id, chunk_ids=chunk_ids)
        if not rows:
            return {"indexed": 0, "skipped": 0}

        to_embed: list[dict[str, Any]] = []
        skipped = 0
        for row in rows:
            digest = content_sha256(row["text"])
            existing = self._knowledge.get_embedding_record(workspace_id, row["chunk_id"], model_ref)
            if existing and existing.get("content_sha256") == digest:
                skipped += 1
                continue
            to_embed.append({**row, "content_sha256": digest})

        if not to_embed:
            return {"indexed": 0, "skipped": skipped}

        texts = [r["text"] for r in to_embed]
        vectors, used_ref = embed_texts(texts, settings)
        if used_ref != model_ref:
            model_ref = used_ref
        dimension = int(vectors.shape[1])

        ids = [r["chunk_id"] for r in to_embed]
        metadata = [
            {
                "workspace_id": workspace_id,
                "document_id": r["document_id"],
                "version_id": r["version_id"],
            }
            for r in to_embed
        ]
        self._backend(workspace_id).upsert(
            workspace_id,
            vectors,
            ids=ids,
            metadata=metadata,
            model_ref=model_ref,
        )

        for row in to_embed:
            self._knowledge.upsert_embedding_record(
                workspace_id,
                chunk_id=row["chunk_id"],
                model_ref=model_ref,
                dimension=dimension,
                content_sha256=row["content_sha256"],
                vector_key=row["chunk_id"],
            )

        return {"indexed": len(to_embed), "skipped": skipped}

    def index_version(self, workspace_id: str, version_id: str) -> dict[str, Any]:
        rows = self._knowledge.list_chunks_for_version(workspace_id, version_id)
        return self.index_chunks(workspace_id, [r["id"] for r in rows])

    def reindex_workspace(self, workspace_id: str) -> dict[str, Any]:
        self._knowledge.delete_all_embedding_records(workspace_id)
        self._backend(workspace_id).reset(workspace_id)
        return self.index_chunks(workspace_id, chunk_ids=None)

    def clear_workspace_vectors(self, workspace_id: str) -> None:
        """Drop all chunk vectors for a workspace (ledger rows may already be gone)."""
        self._knowledge.delete_all_embedding_records(workspace_id)
        self._backend(workspace_id).reset(workspace_id)

    def status(self, workspace_id: str) -> dict[str, Any]:
        config = self._knowledge.get_search_config(workspace_id)
        manifest = self._backend(workspace_id).manifest(workspace_id)
        embed_settings = self._embed_settings(workspace_id)
        current_model_ref = self._current_model_ref(workspace_id)
        indexed_model_ref = manifest.get("model_ref")
        vector_state = "not_indexed"
        if not config.semantic_enabled:
            vector_state = "disabled"
        elif manifest.get("dimension"):
            vector_state = (
                "ready" if indexed_model_ref == current_model_ref else "stale"
            )
        return {
            "storage_ready": True,
            "keyword_ready": config.keyword_enabled,
            "vector_state": vector_state,
            "embedding_configured": bool(
                embed_settings.get("model") and embed_settings.get("api_key")
            ),
            "model_ref": indexed_model_ref,
            "dimension": manifest.get("dimension"),
        }

    def search(
        self,
        workspace_id: str,
        *,
        query: str,
        limit: int = 10,
        document_id: str | None = None,
        entity_id: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        as_of: str | None = None,
        mode: SearchMode | None = None,
    ) -> dict[str, Any]:
        query = query.strip()
        if not query:
            return {"query": query, "mode": "none", "chunks": []}

        config = self._knowledge.get_search_config(workspace_id)
        requested_mode = mode or config.default_mode
        if requested_mode == "keyword" and not config.keyword_enabled:
            raise AdminError(409, "search_mode_disabled", "该工作区未启用全文搜索")
        if requested_mode == "semantic" and not config.semantic_enabled:
            raise AdminError(409, "search_mode_disabled", "该工作区未启用语义搜索")
        if requested_mode == "hybrid" and not (
            config.keyword_enabled and config.semantic_enabled
        ):
            raise AdminError(409, "search_mode_disabled", "该工作区未启用混合搜索")

        limit = min(max(1, limit), 50)
        allow = self._chunk_filter_ids(
            workspace_id,
            document_id=document_id,
            entity_id=entity_id,
            created_after=created_after,
            created_before=created_before,
        )

        keyword_hits = (
            self._knowledge.search_chunks_keyword(workspace_id, query=query, limit=limit * 3)
            if requested_mode in ("keyword", "hybrid")
            else []
        )
        if allow is not None:
            keyword_hits = [h for h in keyword_hits if h["chunk_id"] in allow]

        keyword_rank = [h["chunk_id"] for h in keyword_hits]
        vector_rank: list[str] = []
        effective_mode = "keyword"
        warnings: list[str] = []
        backend = self._backend(workspace_id)
        manifest = backend.manifest(workspace_id)
        model_ref = manifest.get("model_ref") or self._current_model_ref(workspace_id)

        if requested_mode in ("semantic", "hybrid") and manifest.get("dimension"):
            try:
                settings = self._embed_settings(workspace_id)
                qvec, q_ref = embed_query(query, settings)
                if q_ref == model_ref or not manifest.get("model_ref"):
                    filt: dict[str, Any] | None = None
                    if document_id or created_after or created_before:
                        filt = {}
                        if document_id:
                            filt["document_id"] = document_id
                        if created_after:
                            filt["created_after"] = created_after
                        if created_before:
                            filt["created_before"] = created_before
                    raw = backend.search(
                        workspace_id, qvec, limit=limit * 3, filters=filt
                    )
                    for hit in raw:
                        cid = str(hit.get("id", ""))
                        if allow is not None and cid not in allow:
                            continue
                        vector_rank.append(cid)
                    if vector_rank:
                        effective_mode = "hybrid" if keyword_rank else "semantic"
                else:
                    warnings.append("embedding_model_changed_reindex_required")
            except Exception as exc:
                warnings.append(f"vector_search_unavailable:{type(exc).__name__}")
                vector_rank = []
        elif requested_mode in ("semantic", "hybrid"):
            warnings.append("vector_index_not_ready")

        if keyword_rank and vector_rank:
            effective_mode = "hybrid"
            merged = _rrf_merge([keyword_rank, vector_rank], limit)
            chunk_ids = [cid for cid, _ in merged]
        elif vector_rank:
            effective_mode = "semantic"
            chunk_ids = vector_rank[:limit]
        else:
            effective_mode = "keyword" if keyword_rank else "none"
            chunk_ids = keyword_rank[:limit]

        by_id = {h["chunk_id"]: h for h in keyword_hits}
        missing = [cid for cid in chunk_ids if cid not in by_id]
        if missing:
            for row in self._knowledge.get_chunks_by_ids(workspace_id, missing):
                by_id[row["chunk_id"]] = row

        chunks = []
        for cid in chunk_ids:
            row = by_id.get(cid)
            if row:
                chunks.append(row)

        return {
            "query": query,
            "requested_mode": requested_mode,
            "mode": effective_mode,
            "model_ref": manifest.get("model_ref"),
            "warnings": warnings,
            "filters": {
                "document_id": document_id,
                "entity_id": entity_id,
                "created_after": created_after,
                "created_before": created_before,
                "as_of": as_of,
            },
            "chunks": chunks,
        }
