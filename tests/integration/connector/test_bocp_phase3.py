"""Unit tests for BOCP Phase 3: Inbound 4-way sync diff, Outbound writeback with Review gate, and anti-echo loop."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine, text

from basis.services.connector import ConnectorRuntime
from basis.services.knowledge.services.connector_sync import ConnectorLedgerSyncService
from basis.services.knowledge.models import ColumnMappingSpec
from basis.infra.db.sqlite_migrations import run_migrations


def _setup_workspace_and_external_db(
    tmp_path: Path,
) -> tuple[sqlite3.Connection, Path]:
    ext_db_path = tmp_path / "external_crm.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    arr TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        ext_conn.execute(
            text(
                """
                INSERT INTO customers (customer_id, company_name, tier, arr, updated_at)
                VALUES
                    ('c1', 'Alpha Corp', 'silver', '100000', '2026-01-01T00:00:00Z'),
                    ('c2', 'Beta Inc', 'gold', '250000', '2026-01-02T00:00:00Z')
                """
            )
        )
    ext_engine.dispose()

    workspace_db_path = tmp_path / "basis_phase3.db"
    conn = sqlite3.connect(str(workspace_db_path))
    run_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        INSERT INTO users (id, email, display_name, password_hash, is_admin, created_at)
        VALUES ('u1', 'u1@example.com', 'User 1', 'hash', 1, '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO workspaces (id, name, description, visibility, created_by, created_at)
        VALUES ('kb1', 'KB 1', '', 'private', 'u1', '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO ingest_sources (
            id, workspace_id, kind, name, config_json, enabled, created_by, created_at, updated_at
        ) VALUES (
            'src_crm', 'kb1', 'connector', 'CRM Postgres',
            '{"provider":"postgres"}',
            1, 'u1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
        )
        """
    )
    conn.commit()
    return conn, ext_db_path


def test_inbound_4_way_diff_and_outbound_review_writeback_closed_loop(
    tmp_path: Path,
) -> None:
    conn, ext_db_path = _setup_workspace_and_external_db(tmp_path)
    try:
        runtime = ConnectorRuntime(conn, vault_secret="phase3-secret")
        runtime.vault.upsert_connection(
            "kb1",
            "postgres",
            auth_type="database_dsn",
            connection_config={"dsn": f"sqlite:///{ext_db_path}"},
            credentials={"username": "admin", "password": "pw"},
        )

        sync_svc = ConnectorLedgerSyncService(conn, runtime)
        mapping = sync_svc.create_table_mapping(
            "kb1",
            source_id="src_crm",
            stream_name="table_records",
            external_table="customers",
            primary_key_column="customer_id",
            cursor_column="updated_at",
            label_column="company_name",
            target_class_uri="urn:basis:class:Customer",
            column_mappings=[
                ColumnMappingSpec(
                    column="tier",
                    surface_phrase="has customer tier",
                    predicate_uri="urn:basis:prop:tier",
                    writable=True,
                ),
                ColumnMappingSpec(
                    column="arr",
                    surface_phrase="has annual recurring revenue",
                    predicate_uri="urn:basis:prop:arr",
                    writable=False,
                ),
            ],
            sync_mode="full_refresh",
            track_deletes=True,
            sync_direction="bidirectional",
            writeback_mode="review",
        )

        # ── Step 1: Initial Inbound Sync (2 ADDED) ───────────────────────────
        stats1 = sync_svc.sync_inbound_mapping("kb1", mapping.id)
        assert stats1.fetched_rows == 2
        assert stats1.added == 2
        assert stats1.updated == 0
        assert stats1.unchanged == 0
        assert stats1.deleted == 0

        # Verify entities and typed_facts in ledger
        entities = conn.execute(
            "SELECT id, canonical_label FROM entities WHERE workspace_id = 'kb1' AND invalidated_at IS NULL ORDER BY canonical_label"
        ).fetchall()
        assert [(e[1]) for e in entities] == ["Alpha Corp", "Beta Inc"]
        alpha_entity_id = entities[0][0]

        active_facts = conn.execute(
            "SELECT predicate_uri, object_value FROM typed_facts WHERE workspace_id = 'kb1' AND subject_id = ? AND invalidated_at IS NULL",
            (alpha_entity_id,),
        ).fetchall()
        assert dict(active_facts) == {
            "urn:basis:prop:tier": "silver",
            "urn:basis:prop:arr": "100000",
        }

        # ── Step 2: Re-run Inbound Sync with no remote changes (2 UNCHANGED) ─
        stats2 = sync_svc.sync_inbound_mapping("kb1", mapping.id)
        assert stats2.added == 0
        assert stats2.updated == 0
        assert stats2.unchanged == 2
        assert stats2.deleted == 0

        # ── Step 3: Modify c1 & delete c2 in remote DB (1 UPDATED, 1 DELETED) ─
        ext_engine = create_engine(f"sqlite:///{ext_db_path}")
        with ext_engine.begin() as ext_conn:
            ext_conn.execute(
                text(
                    "UPDATE customers SET tier = 'gold', updated_at = '2026-01-05T00:00:00Z' WHERE customer_id = 'c1'"
                )
            )
            ext_conn.execute(
                text("DELETE FROM customers WHERE customer_id = 'c2'")
            )
        ext_engine.dispose()

        stats3 = sync_svc.sync_inbound_mapping("kb1", mapping.id)
        assert stats3.added == 0
        assert stats3.updated == 1
        assert stats3.unchanged == 0
        assert stats3.deleted == 1

        # Verify c1's old tier fact was superseded and new tier fact is 'gold'
        tier_facts = conn.execute(
            "SELECT object_value, invalidated_at FROM typed_facts WHERE workspace_id = 'kb1' AND subject_id = ? AND predicate_uri = 'urn:basis:prop:tier' ORDER BY recorded_at ASC",
            (alpha_entity_id,),
        ).fetchall()
        assert len(tier_facts) == 2
        assert tier_facts[0][0] == "silver" and tier_facts[0][1] is not None
        assert tier_facts[1][0] == "gold" and tier_facts[1][1] is None

        # ── Step 4: Propose Outbound Writeback (non-writable column blocked) ──
        with pytest.raises(PermissionError, match="not marked writable"):
            sync_svc.propose_entity_writeback(
                "kb1",
                entity_id=alpha_entity_id,
                field_updates={"arr": "500000"},
                created_by="u1",
            )

        # Propose valid writeback on writable column 'tier': 'gold' -> 'platinum'
        outbox = sync_svc.propose_entity_writeback(
            "kb1",
            entity_id=alpha_entity_id,
            field_updates={"tier": "platinum"},
            created_by="u1",
        )
        assert outbox["status"] == "pending_review"
        assert outbox["review_item_id"] is not None
        assert outbox["patch"]["changes"]["tier"]["old"] == "gold"
        assert outbox["patch"]["changes"]["tier"]["new"] == "platinum"

        # ── Step 5: Approve & Execute Outbox Writeback ───────────────────────
        executed = sync_svc.approve_and_execute_outbox(
            "kb1",
            outbox["id"],
            actor_id="u1",
            rationale="Customer signed enterprise renewal",
        )
        assert executed["status"] == "synced"
        assert executed["decision_id"] is not None
        assert executed["synced_at"] is not None

        # Verify remote SQLite database actually received 'platinum'
        ext_engine = create_engine(f"sqlite:///{ext_db_path}")
        with ext_engine.connect() as ext_conn:
            remote_tier = ext_conn.execute(
                text("SELECT tier FROM customers WHERE customer_id = 'c1'")
            ).scalar()
        ext_engine.dispose()
        assert remote_tier == "platinum"

        # ── Step 6: Anti-echo loop verification ──────────────────────────────
        # Immediately running inbound sync should see 1 UNCHANGED (0 UPDATED)
        # because execute_outbox_item recomputed and updated row_hash!
        stats4 = sync_svc.sync_inbound_mapping("kb1", mapping.id)
        assert stats4.fetched_rows == 1
        assert stats4.unchanged == 1
        assert stats4.updated == 0
        assert stats4.added == 0
    finally:
        conn.close()
