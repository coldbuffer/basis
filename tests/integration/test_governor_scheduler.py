"""Scheduled governor passes (F-GOV-04 Phase B)."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.governance_config import GovernanceConfig
from basis.domain.knowledge.services.governor_unmapped_types import UNMAPPED_ENTITY_TYPE_KIND
from basis.domain.knowledge.schedulers.governor_poll_scheduler import run_due_governor_passes
from basis.domain.knowledge.schedulers.governor_poll_due import is_governor_due
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.graph.projection.snapshot_store import GraphPersistence
from tests.integration.ontology_hub_sidecar import write_alignment_sidecar


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("sched@example.com", "password1", "Sched")
    workspace_id = admin.create_workspace(user, "Sched KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def test_is_governor_due_when_enabled_and_never_run(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    store.update_governance_config(
        workspace_id,
        governor_enabled=True,
        governor_interval_minutes=60,
        governor_confidence_min=0.8,
    )
    config = store.get_governance_config(workspace_id)
    now = datetime.now(timezone.utc)
    assert is_governor_due(config, now) is True


def test_run_due_governor_passes_executes(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    store.update_governance_config(
        workspace_id,
        governor_enabled=True,
        governor_interval_minutes=60,
        governor_confidence_min=0.75,
    )
    app = MagicMock()
    app.state.knowledge_store = store
    app.state.graph_persistence = GraphPersistence(tmp_path)
    ran = run_due_governor_passes(app)
    assert ran == 1
    config = store.get_governance_config(workspace_id)
    assert config.governor_last_run_at is not None


def test_governor_disabled_not_due(tmp_path: Path) -> None:
    config = GovernanceConfig(workspace_id="x", governor_enabled=False, governor_interval_minutes=60)
    assert is_governor_due(config, datetime.now(timezone.utc)) is False


def _chunk(store: KnowledgeStore, workspace_id: str) -> str:
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="sched-doc",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="evidence")
    store.set_version_status(workspace_id, version_id, "ready")
    return chunk_id


def test_scheduled_governor_unmapped_reads_alignment_sidecar(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    subject = store.create_entity(workspace_id, canonical_label="Sched")
    store.add_open_statement(
        workspace_id,
        subject_id=subject,
        surface_phrase="是",
        object_entity_id=None,
        object_value="鸟",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是鸟",
    )
    store.update_governance_config(
        workspace_id,
        governor_enabled=True,
        governor_interval_minutes=60,
        governor_confidence_min=0.75,
    )
    persistence = GraphPersistence(tmp_path)
    write_alignment_sidecar(
        persistence,
        workspace_id,
        {
            "a1": {
                "id": "a1",
                "source_uri": "http://example.org/a#Bird",
                "target_uri": "https://schema.org/Bird",
                "source_label": "鸟",
                "target_label": "Bird",
                "relation": "skos:exactMatch",
                "confidence": 0.9,
            }
        },
    )
    app = MagicMock()
    app.state.knowledge_store = store
    app.state.graph_persistence = persistence
    assert run_due_governor_passes(app) == 1

    items = store.list_review_items(workspace_id, kind=UNMAPPED_ENTITY_TYPE_KIND)
    assert len(items) == 1
    hints = items[0]["payload"].get("vocabulary_alignment_suggestions") or []
    assert any(row.get("uri") == "http://example.org/a#Bird" for row in hints)
