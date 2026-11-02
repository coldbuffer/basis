"""Unit tests for BOCP Phase 1: ConnectorCatalog, structured_models, and 0011 relational integrity."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3

import yaml

from basis.services.connector import get_connector_catalog
from basis.services.connector.catalog import ConnectorCatalog
from basis.services.connector.manifest.manifest_actions import entity_action_from_stream
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    ProviderSpecReference,
    RetrieverSpec,
    StreamSpec,
)
from basis.services.connector.catalog import default_providers_dir
from basis.services.connector.manifest.provider_bundle import (
    load_connector_manifest,
    load_provider_bundle,
    manifest_wire_payload,
    provider_manifest_path,
    write_provider_bundle,
)
from basis.services.knowledge.models import (
    ColumnMappingSpec,
    ConnectorSourceConfig,
    OutboxFieldChange,
    OutboxPatchSpec,
    StructuredImportProvenance,
    compute_canonical_row_hash,
)
from basis.infra.db.sqlite_migrations import run_migrations


def test_provider_sql_bundle_without_openapi(tmp_path: Path) -> None:
    manifest = ConnectorManifest(
        service="erp-db",
        display_name="ERP DB",
        spec=ProviderSpecReference(protocol="sql", openapi=None),
        auth=[
            AuthSpec(
                auth_mode="database_dsn",
                connection_config=[],
                credentials=[],
            )
        ],
        actions=[
            entity_action_from_stream(
                StreamSpec(
                    name="table_records",
                    display_name="Rows",
                    retriever=RetrieverSpec(adapter="sql_alchemy"),
                )
            )
        ],
    )
    write_provider_bundle(tmp_path, manifest)
    assert not (tmp_path / "erp-db.openapi.yaml").exists()
    loaded = load_provider_bundle(provider_manifest_path(tmp_path, "erp-db"))
    assert loaded.paths.protocol == "sql"
    assert loaded.paths.openapi is None


def test_provider_rest_bundle_requires_openapi(tmp_path: Path) -> None:
    manifest = ConnectorManifest(
        service="sample-api",
        display_name="Sample API",
        spec=ProviderSpecReference(protocol="rest", openapi="openapi.yaml"),
        auth=[
            AuthSpec(
                auth_mode="api_key",
                base_url="https://api.example.com",
                headers={"Authorization": "Bearer ${credentials.api_key}"},
                credentials=[
                    ConfigFieldSpec(
                        key="api_key",
                        label="API Key",
                        input_type="password",
                        required=True,
                        secret=True,
                    )
                ],
            )
        ],
        actions=[],
    )
    write_provider_bundle(tmp_path, manifest)
    manifest_path = provider_manifest_path(tmp_path, "sample-api")
    loaded = load_connector_manifest(manifest_path)
    assert loaded.service == "sample-api"
    assert manifest_path.is_file()
    assert not (tmp_path / "sample-api.openapi.yaml").exists()

    mini = ConnectorCatalog.load_from_directory(tmp_path)
    assert mini.get("sample-api") is not None


def test_connector_catalog_loads_shipped_providers_from_disk() -> None:
    catalog = get_connector_catalog()
    stats = catalog.summary_stats()
    assert stats["providers"] == 4
    assert stats["providers_with_streams"] == 3

    pg = catalog.get("postgres")
    assert pg is not None
    assert pg.spec is not None
    assert pg.spec.protocol == "sql"
    assert pg.auth[0].auth_mode == "database_dsn"
    assert len(pg.streams) == 1
    assert pg.streams[0].dynamic_schema_loader is not None
    assert pg.streams[0].dynamic_schema_loader.type == "sql_inspector"
    assert pg.streams[0].retriever.adapter == "sql_alchemy"
    assert "update" in pg.streams[0].mutations

    mysql = catalog.get("mysql")
    assert mysql is not None
    assert mysql.spec is not None
    assert mysql.spec.protocol == "sql"
    assert mysql.auth[0].auth_mode == "database_dsn"

    db_connectors = catalog.list_manifests(category="Database", has_streams_only=True)
    db_services = {m.service for m in db_connectors}
    assert db_services == {"postgres", "mysql"}

    gh = catalog.get("github")
    assert gh is not None
    assert gh.spec is not None
    assert gh.spec.protocol == "rest"
    assert gh.streams[0].retriever.adapter == "rest_declarative"
    gh_paths = catalog.provider_bundle_paths("github")
    assert gh_paths is not None
    assert gh_paths.manifest_path.name == "github.yaml"
    assert gh_paths.openapi is None
    assert len(gh.procedure_actions()) == 1
    assert gh.procedure_actions()[0].id == "get_authenticated_user"


def test_shipped_connector_yaml_matches_manifest_wire_payload() -> None:
    """On-disk ``connector.yaml`` for shipped providers follows ``manifest_wire_payload`` layout."""
    for name in ("github", "postgres", "mysql"):
        providers_root = default_providers_dir()
        manifest_path = provider_manifest_path(providers_root, name)
        loaded = load_provider_bundle(manifest_path)
        expected = yaml.safe_dump(
            manifest_wire_payload(loaded.manifest),
            sort_keys=False,
            allow_unicode=True,
        )
        on_disk = manifest_path.read_text(encoding="utf-8")
        assert on_disk == expected
        assert on_disk.startswith("version:")
        assert loaded.manifest.actions
        if name == "github":
            assert len(loaded.manifest.entity_actions()) == 2
            assert len(loaded.manifest.procedure_actions()) == 1
        else:
            assert all(a.kind == "entity" for a in loaded.manifest.actions)


def test_canonical_row_hash_determinism_and_normalization() -> None:
    mappings = [
        ColumnMappingSpec(column="b_amount", surface_phrase="amount"),
        ColumnMappingSpec(column="a_date", surface_phrase="date"),
        ColumnMappingSpec(column="c_ts", surface_phrase="timestamp"),
        ColumnMappingSpec(column="d_nested", surface_phrase="metadata"),
    ]
    row_a = {
        "company_name": "Acme",
        "b_amount": Decimal("120.50"),
        "a_date": date(2026, 10, 19),
        "c_ts": datetime(2026, 10, 19, 10, 30, 0),
        "d_nested": {"z": 1, "a": 2},
        "unmapped_extra": "ignored_in_hash",
    }
    row_b = {
        "company_name": "Acme",
        "d_nested": {"a": 2, "z": 1},
        "c_ts": "2026-10-19T10:30:00",
        "a_date": "2026-10-19",
        "b_amount": "120.50",
        "unmapped_extra": "different_unmapped_value",
    }
    hash_a = compute_canonical_row_hash(
        row_a, label_column="company_name", column_mappings=mappings
    )
    hash_b = compute_canonical_row_hash(
        row_b, label_column="company_name", column_mappings=mappings
    )
    assert len(hash_a) == 64
    assert hash_a == hash_b

    row_c = dict(row_b, b_amount="120.51")
    assert (
        compute_canonical_row_hash(
            row_c, label_column="company_name", column_mappings=mappings
        )
        != hash_a
    )


def test_structured_models_validation() -> None:
    src_cfg = ConnectorSourceConfig(
        provider="postgres",
        poll_interval_minutes=30,
    )
    assert src_cfg.provider == "postgres"

    mapping = ColumnMappingSpec(
        column="customer_tier",
        kind="literal",
        surface_phrase="customer tier",
        predicate_uri="urn:basis:prop:customer_tier",
        writable=True,
    )
    assert mapping.writable is True

    prov = StructuredImportProvenance(
        provider="postgres",
        stream="table_records",
        source_id="src_1",
        mapping_id="map_1",
        external_ref_id="ref_1",
        external_table="public.customers",
        external_pk="cust_001",
        column="customer_tier",
    )
    assert prov.kind == "structured_source"

    patch = OutboxPatchSpec(
        provider="postgres",
        stream_name="table_records",
        mutation_operation="update",
        external_table="public.customers",
        primary_key_column="customer_id",
        external_pk="cust_001",
        changes={
            "customer_tier": OutboxFieldChange(old="silver", new="gold"),
        },
    )
    assert patch.changes["customer_tier"].new == "gold"


def test_0011_tables_foreign_keys_and_unique_constraints(tmp_path: Path) -> None:
    db = tmp_path / "bocp.db"
    conn = sqlite3.connect(str(db))
    run_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
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
            INSERT INTO connector_connections (
                workspace_id, service, connection_scope, subject_id, auth_type,
                connection_config_json, value_encrypted, account_profile_json, revision, updated_at
            ) VALUES (
                'kb1', 'postgres', 'workspace', '', 'database_dsn',
                '{"host":"localhost"}', 'enc_secret', '{}', 1, '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ingest_sources (
                id, workspace_id, kind, name, config_json, enabled, created_by, created_at, updated_at
            ) VALUES (
                'src1', 'kb1', 'connector', 'Customers DB',
                '{"provider":"postgres"}',
                1, 'u1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO source_table_mappings (
                id, workspace_id, source_id, stream_name, external_table,
                primary_key_column, label_column, target_class_uri,
                column_mappings_json, created_at, updated_at
            ) VALUES (
                'map1', 'kb1', 'src1', 'table_records', 'public.customers',
                'id', 'name', 'urn:basis:class:Customer',
                '[]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO entities (id, workspace_id, canonical_label, entity_kind, created_at)
            VALUES ('ent1', 'kb1', 'Acme Corp', 'named', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO entity_external_refs (
                id, workspace_id, entity_id, source_id, mapping_id,
                external_table, external_pk, row_hash, last_synced_at
            ) VALUES (
                'ref1', 'kb1', 'ent1', 'src1', 'map1',
                'public.customers', 'cust_42', 'abc123hash', '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO agent_decisions (
                id, workspace_id, action, status, confidence, rationale, trace_json, created_at
            ) VALUES (
                'dec1', 'kb1', 'entity_writeback', 'proposed', 0.95,
                'Tier upgraded in contract', '{}', '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO entity_sync_outbox (
                id, workspace_id, entity_id, external_ref_id, action_kind, patch_json,
                status, decision_id, created_by, created_at
            ) VALUES (
                'out1', 'kb1', 'ent1', 'ref1', 'update_fields',
                '{"provider":"postgres","stream_name":"table_records","external_table":"public.customers","primary_key_column":"id","external_pk":"cust_42","changes":{"tier":{"old":"A","new":"S"}}}',
                'pending_review', 'dec1', 'u1', '2026-01-01T00:00:00Z'
            )
            """
        )
        conn.commit()

        row = conn.execute(
            "SELECT status, decision_id FROM entity_sync_outbox WHERE id = 'out1'"
        ).fetchone()
        assert row == ("pending_review", "dec1")
    finally:
        conn.close()
