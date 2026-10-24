"""Provision idempotent demo workspace for a user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.graph.projection.session import GraphSession
from basis.domain.graph.reasoning.forward import infer_with_proof_chains
from basis.domain.knowledge.demo.pack_v1 import (
    DEMO_GROUND_FACTS,
    DEMO_MAPPINGS,
    DEMO_PACK_MARKER,
    DEMO_RULE_BODY,
    DEMO_RULE_NAME,
    LEGACY_DEMO_DOC_KEYS,
    PACK_CHECK_EXTERNAL_KEY,
    SEED_DOCS,
)
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.domain.knowledge.pipeline.version_ingest import run_version_ingest
from basis.domain.knowledge.services.derived_facts_service import persist_reasoning_derived

if TYPE_CHECKING:
    from basis.domain.graph.projection.snapshot_store import GraphPersistence
    from basis.domain.graph.session.registry import GraphSessionRegistry
    from basis.domain.knowledge.store import KnowledgeStore


def _iso(dt: str) -> str:
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


def find_demo_workspace_id(conn: Any, user_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT w.id FROM workspaces w
        JOIN members m ON m.workspace_id = w.id AND m.user_id = ? AND m.role = 'owner'
        WHERE w.description LIKE ?
        LIMIT 1
        """,
        (user_id, f"%{DEMO_PACK_MARKER}%"),
    ).fetchone()
    return row[0] if row else None


def _chunk_for(conn: Any, workspace_id: str, external_key: str) -> str:
    row = conn.execute(
        """
        SELECT c.id FROM chunks c
        JOIN document_versions v ON v.id = c.version_id
        JOIN documents d ON d.id = v.document_id
        WHERE c.workspace_id = ? AND d.external_key = ?
        LIMIT 1
        """,
        (workspace_id, external_key),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing chunk for external_key={external_key}")
    return row[0]


def _seed_manual_statements(knowledge: KnowledgeStore, workspace_id: str, actor_id: str) -> None:
    conn = knowledge._conn
    if conn.execute(
        """
        SELECT 1 FROM statement_evidence e
        JOIN statements s ON s.id = e.statement_id
        WHERE s.workspace_id = ? AND e.quote = ?
        LIMIT 1
        """,
        (workspace_id, "北辰科技2026年度续费报价请联系商务经理唐悦确认"),
    ).fetchone():
        return

    beichen = knowledge.get_or_create_entity_by_label(workspace_id, "北辰科技")
    yundun = knowledge.get_or_create_entity_by_label(workspace_id, "云盾科技")
    cheng_hao = knowledge.get_or_create_entity_by_label(workspace_id, "程浩")
    tang_yue = knowledge.get_or_create_entity_by_label(workspace_id, "唐悦")
    lao_zhou = knowledge.get_or_create_entity_by_label(workspace_id, "老周")
    hq = knowledge.get_or_create_entity_by_label(workspace_id, "北辰科技总部大楼")

    seeds = [
        (
            "2025-08-01T09:00:00+00:00",
            "yundun-impl-2025",
            beichen,
            "签署年度服务协议",
            yundun,
            None,
            "北辰科技与云盾科技签署年度服务协议",
        ),
        (
            "2025-08-01T09:05:00+00:00",
            "yundun-impl-2025",
            cheng_hao,
            "项目实施对接",
            yundun,
            None,
            "程浩为云盾科技侧项目实施对接人",
        ),
        (
            "2026-01-10T10:00:00+00:00",
            "yundun-renewal-2026",
            tang_yue,
            "续费报价联系",
            yundun,
            None,
            "北辰科技2026年度续费报价请联系商务经理唐悦确认",
        ),
        (
            "2026-02-01T08:00:00+00:00",
            "facility-inspection-2026",
            lao_zhou,
            "空调巡检对接",
            hq,
            None,
            "物业老周为现场对接负责人",
        ),
    ]
    for recorded_at, external_key, subj, phrase, obj_ent, obj_val, quote in seeds:
        sid = knowledge.add_open_statement(
            workspace_id,
            subject_id=subj,
            surface_phrase=phrase,
            object_entity_id=obj_ent,
            object_value=obj_val,
            status="confirmed",
            proposed_by=actor_id,
            chunk_id=_chunk_for(conn, workspace_id, external_key),
            quote=quote,
        )
        conn.execute("UPDATE statements SET recorded_at = ? WHERE id = ?", (recorded_at, sid))
    conn.commit()


def _purge_legacy_demo_documents(knowledge: KnowledgeStore, workspace_id: str) -> None:
    if knowledge.find_document_by_external_key(workspace_id, PACK_CHECK_EXTERNAL_KEY) is not None:
        return
    for external_key in LEGACY_DEMO_DOC_KEYS:
        doc = knowledge.find_document_by_external_key(workspace_id, external_key)
        if doc is None:
            continue
        knowledge.hard_delete_document(workspace_id, doc["document_id"])
    conn = knowledge._conn
    conn.execute(
        """
        DELETE FROM derived_facts
        WHERE workspace_id = ? AND predicate_uri LIKE ?
        """,
        (workspace_id, "%accountablePartnershipLead%"),
    )
    conn.commit()


def _mark_workspace_demo_pack(knowledge: KnowledgeStore, workspace_id: str) -> None:
    conn = knowledge._conn
    row = conn.execute(
        "SELECT description FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    if row is None:
        return
    desc = (row[0] or "").strip()
    if DEMO_PACK_MARKER in desc:
        return
    suffix = DEMO_PACK_MARKER
    new_desc = f"{desc}\n{suffix}".strip() if desc else suffix
    conn.execute(
        "UPDATE workspaces SET description = ? WHERE id = ?",
        (new_desc, workspace_id),
    )
    conn.commit()


def _ensure_ontology_mappings(knowledge: KnowledgeStore, workspace_id: str, actor_id: str) -> None:
    confirmed = {
        row["signature"]: row["id"]
        for row in knowledge.list_mappings(workspace_id, status="confirmed", limit=200)
    }
    for signature, predicate_uri in DEMO_MAPPINGS:
        mapping_id = confirmed.get(signature)
        if mapping_id is None:
            created = knowledge.create_mapping(
                workspace_id,
                actor_id,
                signature=signature,
                target_uri=predicate_uri,
                target_kind="property",
                direction="forward",
                status="confirmed",
                why="demo_pack",
            )
            mapping_id = created["id"]
            confirmed[signature] = mapping_id
        knowledge.materialize_mapping_facts(workspace_id, mapping_id)


def _ensure_reasoning_rule(knowledge: KnowledgeStore, workspace_id: str, actor_id: str) -> None:
    for row in knowledge.list_reasoning_rules(workspace_id, limit=50):
        if (row.get("body") or "").strip() == DEMO_RULE_BODY:
            return
    knowledge.create_reasoning_rule(
        workspace_id,
        name=DEMO_RULE_NAME,
        body=DEMO_RULE_BODY,
        actor_id=actor_id,
        enabled=True,
    )


def _apply_demo_reasoning(knowledge: KnowledgeStore, workspace_id: str) -> None:
    from basis.domain.knowledge.reasoning_ground_facts import ground_fact_strings_from_typed_facts

    facts = ground_fact_strings_from_typed_facts(knowledge, workspace_id)
    if not facts:
        facts = list(DEMO_GROUND_FACTS)
    rules = [DEMO_RULE_BODY]
    _, proofs = infer_with_proof_chains(facts, rules)
    if not proofs:
        return
    persist_reasoning_derived(
        knowledge,
        workspace_id,
        [proof.as_dict() for proof in proofs],
    )


def _rebuild_graph(
    knowledge: KnowledgeStore,
    workspace_id: str,
    persistence: GraphPersistence,
    registry: GraphSessionRegistry | None,
) -> None:
    session = GraphSession()
    apply_rebuild_to_session(knowledge, workspace_id, session)
    state = knowledge.get_projection_state(workspace_id)
    persistence.save(
        workspace_id,
        session,
        projection_revision=state["revision"],
        schema_version=state["schema_version"],
    )
    if registry is not None:
        registry.invalidate(workspace_id)


def _load_pack_content(
    knowledge: KnowledgeStore,
    workspace_id: str,
    actor_id: str,
    *,
    persistence: GraphPersistence,
    registry: GraphSessionRegistry | None,
) -> None:
    _mark_workspace_demo_pack(knowledge, workspace_id)
    _purge_legacy_demo_documents(knowledge, workspace_id)

    if knowledge.find_document_by_external_key(workspace_id, PACK_CHECK_EXTERNAL_KEY) is not None:
        _ensure_ontology_mappings(knowledge, workspace_id, actor_id)
        _ensure_reasoning_rule(knowledge, workspace_id, actor_id)
        _apply_demo_reasoning(knowledge, workspace_id)
        _rebuild_graph(knowledge, workspace_id, persistence, registry)
        return

    graph = GraphSession()
    ingested_versions: list[tuple[str, str, str]] = []

    for external_key, title, recorded_at, text in SEED_DOCS:
        if knowledge.find_document_by_external_key(workspace_id, external_key) is not None:
            continue
        outcome = knowledge.store_document_bytes(
            workspace_id,
            title=title,
            mime_type="text/plain",
            data=text.encode("utf-8"),
            created_by=actor_id,
            original_filename=title,
            external_key=external_key,
        )
        job, _ = knowledge.create_processing_job(
            workspace_id,
            version_id=outcome.version_id,
            options={"extract": True, "chunk": True},
        )
        run_version_ingest(
            knowledge,
            graph,
            workspace_id,
            outcome.version_id,
            job["id"],
            filename=title,
            graph_doc_id=external_key,
            options=TextIngestOptions(extract=True, chunk=True),
        )
        ingested_versions.append((outcome.version_id, external_key, _iso(recorded_at)))

    conn = knowledge._conn
    for version_id, external_key, recorded_at in ingested_versions:
        chunk_rows = conn.execute(
            """
            SELECT c.id FROM chunks c
            WHERE c.workspace_id = ? AND c.version_id = ?
            """,
            (workspace_id, version_id),
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
            (recorded_at, workspace_id, workspace_id, *chunk_ids),
        )
        conn.execute(
            """
            UPDATE documents SET created_at = ?
            WHERE workspace_id = ? AND external_key = ?
            """,
            (recorded_at, workspace_id, external_key),
        )
    conn.commit()

    _seed_manual_statements(knowledge, workspace_id, actor_id)
    _ensure_ontology_mappings(knowledge, workspace_id, actor_id)
    _ensure_reasoning_rule(knowledge, workspace_id, actor_id)
    _apply_demo_reasoning(knowledge, workspace_id)
    _rebuild_graph(knowledge, workspace_id, persistence, registry)


def load_demo_pack_into_workspace(
    *,
    knowledge: KnowledgeStore,
    graph_persistence: GraphPersistence,
    graph_registry: GraphSessionRegistry | None,
    workspace_id: str,
    actor_id: str,
) -> None:
    """Import demo documents, ontology mappings, and reasoning into an existing workspace."""
    _load_pack_content(
        knowledge,
        workspace_id,
        actor_id,
        persistence=graph_persistence,
        registry=graph_registry,
    )


def load_demo_pack_from_request(request: Any, workspace_id: str, actor_id: str) -> None:
    load_demo_pack_into_workspace(
        knowledge=request.app.state.knowledge_store,
        graph_persistence=request.app.state.graph_persistence,
        graph_registry=getattr(request.app.state, "graph_session_registry", None),
        workspace_id=workspace_id,
        actor_id=actor_id,
    )
