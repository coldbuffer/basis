#!/usr/bin/env python3
"""Seed a dedicated workspace with deterministic chunk-search benchmark data."""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from basis.domain.tenancy.admin.store import AdminStore
from basis.infra.runtime.config import Settings
from basis.infra.runtime.database import get_database
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore

KB_NAME = "Search Benchmark"
LEGACY_KB_NAMES = {"Search Benchmark 10k", "Search Benchmark 100k"}
TOPICS = (
    ("合同", "contract", "供应商应在三十日内完成交付并提供验收材料。"),
    ("巴黎", "paris", "巴黎是法国的重要城市，埃菲尔铁塔是著名地标。"),
    ("数据库", "database", "SQLite 使用 WAL 模式处理并发读取和顺序写入。"),
    ("检索", "retrieval", "混合检索融合全文关键词与语义向量的排序结果。"),
    ("安全", "security", "访问控制遵循最小权限原则并记录完整审计事件。"),
    ("财务", "finance", "季度预算包括研发、基础设施和客户支持成本。"),
    ("医疗", "healthcare", "临床记录需要保留来源、时间和审核状态。"),
    ("物流", "logistics", "仓库根据订单优先级规划库存补充与配送路径。"),
    ("能源", "energy", "可再生能源项目评估发电效率与长期维护成本。"),
    ("教育", "education", "课程设计结合学习目标、练习和阶段性评估。"),
)


def chunk_text(document_no: int, ordinal: int) -> str:
    topic_zh, topic_en, sentence = TOPICS[(document_no + ordinal) % len(TOPICS)]
    rng = random.Random(document_no * 100_003 + ordinal)
    reference = rng.randint(100_000, 999_999)
    return (
        f"基准文档 {document_no:04d}，片段 {ordinal:03d}，主题：{topic_zh} / {topic_en}。"
        f"{sentence} 本段用于测试关键词、过滤、分页和排序性能。"
        f"唯一引用编号 BENCH-{reference}。"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=100)
    parser.add_argument("--chunks-per-document", type=int, default=100)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--database-url")
    args = parser.parse_args()
    if args.documents < 1 or args.chunks_per_document < 1:
        parser.error("document and chunk counts must be positive")

    settings = Settings.from_env()
    data_dir = args.data_dir or settings.data_dir
    database_url = args.database_url or (
        settings.effective_database_url
        if not args.data_dir
        else f"sqlite:///{(data_dir / 'basis.db').resolve()}"
    )
    database = get_database(database_url)
    admin = AdminStore(database)
    knowledge = KnowledgeStore(database, BlobStore(data_dir))

    try:
        users = admin.list_users()
        if not users:
            raise SystemExit("Create a Basis user before seeding benchmark data.")
        owner = users[0]
        kb = next(
            (
                item
                for item in admin.list_visible_workspaces(owner)
                if item.name == KB_NAME or item.name in LEGACY_KB_NAMES
            ),
            None,
        )
        if kb is None:
            kb = admin.create_workspace(
                owner,
                KB_NAME,
                "Deterministic synthetic data for retrieval performance tests.",
                "restricted",
            )
        elif kb.name != KB_NAME:
            kb = admin.update_workspace(owner, kb.id, name=KB_NAME)

        stats = knowledge.workspace_mcp_stats(kb.id)
        target = args.documents * args.chunks_per_document
        existing = stats["chunk_count"]
        if existing >= target:
            print(f"{KB_NAME}: already has {existing:,} chunks; nothing to add")
            print(f"workspace_id={kb.id}")
            return

        docs_to_add = math.ceil((target - existing) / args.chunks_per_document)
        start_doc = stats["document_count"]
        for offset in range(docs_to_add):
            document_no = start_doc + offset
            texts = [
                chunk_text(document_no, ordinal)
                for ordinal in range(args.chunks_per_document)
            ]
            source = "\n\n".join(texts).encode("utf-8")
            _, version_id, job_id, _ = knowledge.store_upload_bytes(
                kb.id,
                title=f"benchmark-{document_no:04d}.txt",
                mime_type="text/plain",
                data=source,
                created_by=owner.id,
                external_key=f"benchmark-{document_no:04d}",
            )
            knowledge.set_job_status(kb.id, job_id, "running")
            knowledge.set_version_status(kb.id, version_id, "chunking")
            knowledge.create_chunks(kb.id, version_id, texts)
            knowledge.set_version_status(kb.id, version_id, "ready")
            knowledge.set_job_status(kb.id, job_id, "succeeded")

        # Keep this dataset cheap to seed: keyword search is enabled, vector
        # indexing can be turned on later from workspace settings when benchmarking it.
        knowledge.update_search_config(
            kb.id,
            embedding_model_id=None,
            keyword_enabled=True,
            semantic_enabled=False,
            default_mode="keyword",
            auto_index=False,
        )
        final = knowledge.workspace_mcp_stats(kb.id)
        print(
            f"{KB_NAME}: {final['document_count']:,} documents, "
            f"{final['chunk_count']:,} chunks"
        )
        print(f"workspace_id={kb.id}")
    finally:
        knowledge.close()
        admin.close()


if __name__ == "__main__":
    main()
