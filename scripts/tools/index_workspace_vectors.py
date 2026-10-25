#!/usr/bin/env python3
"""Batch-index chunk embeddings for a workspace (memory-safe for large workspaces)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from basis.domain.tenancy.admin.store import AdminStore
from basis.infra.runtime.config import Settings
from basis.infra.runtime.database import get_database
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.search import ChunkSearchService
from basis.domain.knowledge.store import KnowledgeStore


def _pending_chunk_ids(database, workspace_id: str, limit: int) -> list[str]:
    rows = database.conn.execute(
        """
        SELECT c.id AS chunk_id
        FROM chunks c
        LEFT JOIN embedding_records e
          ON e.workspace_id = c.workspace_id AND e.chunk_id = c.id
        WHERE c.workspace_id = ? AND e.chunk_id IS NULL
        ORDER BY c.id
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    return [row["chunk_id"] for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-name", default="Search Benchmark")
    parser.add_argument("--kb-id")
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--enable-semantic", action="store_true")
    parser.add_argument("--default-mode", default="hybrid")
    args = parser.parse_args()

    settings = Settings.from_env()
    database = get_database(settings.effective_database_url)
    knowledge = KnowledgeStore(database, BlobStore(settings.data_dir))
    admin = AdminStore(database)
    search = ChunkSearchService(knowledge, admin, Path(settings.data_dir))
    try:
        if args.workspace_id:
            workspace_id = args.workspace_id
        else:
            row = database.conn.execute(
                "SELECT id FROM workspaces WHERE name = ?", (args.workspace_name,)
            ).fetchone()
            if row is None:
                raise SystemExit(f"Workspace not found: {args.workspace_name}")
            workspace_id = row["id"]

        config = knowledge.get_search_config(workspace_id)
        if args.enable_semantic and not config.semantic_enabled:
            knowledge.update_search_config(
                workspace_id,
                embedding_model_id=config.embedding_model_id,
                keyword_enabled=config.keyword_enabled,
                semantic_enabled=True,
                default_mode=args.default_mode,
                auto_index=config.auto_index,
                chunk_backend=config.chunk_backend,
                vector_backend=config.vector_backend,
            )

        total_indexed = 0
        total_skipped = 0
        started = time.perf_counter()
        batch_no = 0
        while True:
            chunk_ids = _pending_chunk_ids(database, workspace_id, args.batch_size)
            if not chunk_ids:
                break
            batch_no += 1
            t0 = time.perf_counter()
            result = search.index_chunks(workspace_id, chunk_ids)
            indexed = int(result.get("indexed", 0))
            skipped = int(result.get("skipped", 0))
            total_indexed += indexed
            total_skipped += skipped
            elapsed = time.perf_counter() - started
            rate = total_indexed / elapsed if elapsed > 0 else 0.0
            print(
                f"batch={batch_no} indexed={indexed} skipped={skipped} "
                f"total={total_indexed} rate={rate:.1f}/s batch_sec={time.perf_counter()-t0:.1f}",
                flush=True,
            )
            if indexed == 0 and skipped == 0:
                print("no progress; stopping", file=sys.stderr)
                break

        print(
            {
                "workspace_id": workspace_id,
                "indexed": total_indexed,
                "skipped": total_skipped,
                "elapsed_sec": round(time.perf_counter() - started, 1),
            },
            flush=True,
        )
    finally:
        knowledge.close()
        admin.close()


if __name__ == "__main__":
    main()
