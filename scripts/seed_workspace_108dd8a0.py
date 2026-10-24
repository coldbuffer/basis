#!/usr/bin/env python3
"""Seed demo ledger + graph data for workspace 108dd8a0 (local dev)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.domain.knowledge.pipeline.version_ingest import run_version_ingest

WORKSPACE_ID = "108dd8a0-297b-4c37-862f-f47da99ae4f3"

SEED_DOCS: list[tuple[str, str, str, str]] = [
    (
        "march-hr-2026",
        "组织人事更新（2026年3月）.txt",
        "2026-03-10T08:00:00+00:00",
        """组织人事更新（2026年3月）

陈磊加入星河科技有限公司，担任数据平台负责人。
周衡向人力资源部推荐陈磊入职。
""",
    ),
    (
        "june-partner-2026",
        "商务合作备忘（2026年6月）.txt",
        "2026-06-15T10:30:00+00:00",
        """商务合作备忘（2026年6月）

星河科技与北海数据有限公司签署战略合作协议。
林夏被任命为对外合作接口人，负责北海数据项目落地。
""",
    ),
    (
        "oct-facility-2026",
        "行政通知（2026年10月）.txt",
        "2026-10-15T06:00:00+00:00",
        """行政通知（2026年10月）

星河科技深圳办公室启用，地址南山区科技园。
周衡负责新办公室网络与安防对接。
""",
    ),
]


def _seed_manual_statements(knowledge, actor_id: str) -> None:
    """Pattern NER misses Chinese; add ledger rows for demo timeline."""
    conn = knowledge._conn
    if conn.execute(
        "SELECT 1 FROM entities WHERE workspace_id = ? AND canonical_label = ? LIMIT 1",
        (WORKSPACE_ID, "陈磊"),
    ).fetchone():
        print("manual statements already present (陈磊 exists)")
        return

    lin_xia = "38a30e07-fc2a-4a84-9b25-90f4d1884bdd"
    zhou = "7220f2f9-2db2-4f85-8920-bb6d43c5ac1a"
    xinghe = "6e891ad2-145f-41c4-976c-ad00b7221784"
    xinghe_ltd = "33d7064b-97b6-4461-99ad-8ff604b8189a"
    chen_lei = knowledge.get_or_create_entity_by_label(WORKSPACE_ID, "陈磊")
    beihai = knowledge.get_or_create_entity_by_label(WORKSPACE_ID, "北海数据有限公司")

    def chunk_for(external_key: str) -> str:
        row = conn.execute(
            """
            SELECT c.id FROM chunks c
            JOIN document_versions v ON v.id = c.version_id
            JOIN documents d ON d.id = v.document_id
            WHERE c.workspace_id = ? AND d.external_key = ?
            LIMIT 1
            """,
            (WORKSPACE_ID, external_key),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"missing chunk for {external_key}")
        return row[0]

    seeds = [
        ("2026-03-10T08:00:00+00:00", chunk_for("march-hr-2026"), chen_lei, "入职于", xinghe_ltd, None, "陈磊加入星河科技有限公司"),
        ("2026-03-10T08:05:00+00:00", chunk_for("march-hr-2026"), zhou, "推荐", chen_lei, None, "周衡向人力资源部推荐陈磊"),
        ("2026-06-15T10:30:00+00:00", chunk_for("june-partner-2026"), xinghe, "合作", beihai, None, "星河科技与北海数据有限公司签署战略合作协议"),
        ("2026-06-15T10:35:00+00:00", chunk_for("june-partner-2026"), lin_xia, "负责", beihai, None, "林夏被任命为对外合作接口人"),
        ("2026-10-15T06:00:00+00:00", chunk_for("oct-facility-2026"), zhou, "负责", xinghe, None, "周衡负责新办公室网络与安防对接"),
    ]
    for recorded_at, chunk_id, subj, phrase, obj_ent, obj_val, quote in seeds:
        sid = knowledge.add_open_statement(
            WORKSPACE_ID,
            subject_id=subj,
            surface_phrase=phrase,
            object_entity_id=obj_ent,
            object_value=obj_val,
            status="confirmed",
            proposed_by=actor_id,
            chunk_id=chunk_id,
            quote=quote,
        )
        conn.execute("UPDATE statements SET recorded_at = ? WHERE id = ?", (recorded_at, sid))
    conn.commit()
    print(f"added {len(seeds)} manual statements")


def _iso(dt: str) -> str:
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


def main() -> int:
    settings = Settings.from_env()
    app = create_app(settings)
    knowledge = app.state.knowledge_store
    store = app.state.store
    persistence: GraphPersistence = app.state.graph_persistence

    conn = knowledge._conn
    if conn.execute("SELECT id FROM workspaces WHERE id = ?", (WORKSPACE_ID,)).fetchone() is None:
        print(f"Workspace not found: {WORKSPACE_ID}", file=sys.stderr)
        return 1

    owner_row = conn.execute(
        "SELECT user_id FROM members WHERE workspace_id = ? AND role = 'owner' LIMIT 1",
        (WORKSPACE_ID,),
    ).fetchone()
    if owner_row is None:
        print("No workspace owner", file=sys.stderr)
        return 1
    actor_id = owner_row[0]

    graph = GraphSession()
    ingested_versions: list[tuple[str, str, str]] = []

    for external_key, title, recorded_at, text in SEED_DOCS:
        existing = knowledge.find_document_by_external_key(WORKSPACE_ID, external_key)
        if existing is not None:
            print(f"skip existing doc external_key={external_key}")
            continue

        outcome = knowledge.store_document_bytes(
            WORKSPACE_ID,
            title=title,
            mime_type="text/plain",
            data=text.encode("utf-8"),
            created_by=actor_id,
            original_filename=title,
            external_key=external_key,
        )
        job, _ = knowledge.create_processing_job(
            WORKSPACE_ID,
            version_id=outcome.version_id,
            options={"extract": True, "chunk": True},
        )
        try:
            run_version_ingest(
                knowledge,
                graph,
                WORKSPACE_ID,
                outcome.version_id,
                job["id"],
                filename=title,
                graph_doc_id=external_key,
                options=TextIngestOptions(extract=True, chunk=True),
            )
        except Exception as exc:
            print(f"ingest failed for {external_key}: {exc}", file=sys.stderr)
            return 1

        ingested_versions.append((outcome.version_id, external_key, _iso(recorded_at)))
        print(f"ingested {external_key} -> version {outcome.version_id}")

    if not ingested_versions:
        print("Nothing new to ingest (documents may already exist).")
    if ingested_versions:
        conn = knowledge._conn
        for version_id, external_key, recorded_at in ingested_versions:
            chunk_rows = conn.execute(
                """
                SELECT c.id FROM chunks c
                JOIN document_versions v ON v.id = c.version_id
                WHERE c.workspace_id = ? AND c.version_id = ?
                """,
                (WORKSPACE_ID, version_id),
            ).fetchall()
            chunk_ids = [row[0] for row in chunk_rows]
            if not chunk_ids:
                continue
            placeholders = ",".join("?" * len(chunk_ids))
            conn.execute(
                f"""
                UPDATE statements
                SET recorded_at = ?
                WHERE workspace_id = ? AND id IN (
                  SELECT statement_id FROM statement_evidence
                  WHERE workspace_id = ? AND chunk_id IN ({placeholders})
                )
                """,
                (recorded_at, WORKSPACE_ID, WORKSPACE_ID, *chunk_ids),
            )
            conn.execute(
                """
                UPDATE documents SET created_at = ?
                WHERE workspace_id = ? AND external_key = ?
                """,
                (recorded_at, WORKSPACE_ID, external_key),
            )
        conn.commit()

    _seed_manual_statements(knowledge, actor_id)

    session = GraphSession()
    meta = apply_rebuild_to_session(knowledge, WORKSPACE_ID, session)
    state = knowledge.get_projection_state(WORKSPACE_ID)
    persistence.save(
        WORKSPACE_ID,
        session,
        projection_revision=state["revision"],
        schema_version=state["schema_version"],
    )
    app.state.graph_session_registry.invalidate(WORKSPACE_ID)

    print(
        "rebuild ok:",
        f"revision={meta.get('projection_revision')}",
        f"nodes={meta.get('node_count')}",
        f"edges={meta.get('edge_count')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
