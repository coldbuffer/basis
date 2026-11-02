"""Unit tests for BOCP Phase 2: AuthVault, SqlAlchemyStreamAdapter, RestDeclarativeStreamAdapter, and ConnectorRuntime."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, text

from basis.services.connector import (
    ConnectorAuthVault,
    ConnectorRuntime,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from basis.services.connector.catalog import ConnectorCatalog, get_connector_catalog
from basis.services.connector.adapters.rest.curated_dev import curated_rest_manifests
from basis.infra.db.sqlite_migrations import run_migrations


@pytest.fixture(autouse=True)
def _phase2_catalog_includes_rest_dev_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shipped catalog is SQL-only; Phase 2 REST tests use in-repo dev manifests."""
    get_connector_catalog.cache_clear()
    shipped = ConnectorCatalog.load_from_directory()
    by_service = {m.service: m for m in shipped.list_manifests()}
    by_service.update(curated_rest_manifests())
    catalog = ConnectorCatalog(list(by_service.values()))

    def _catalog() -> ConnectorCatalog:
        return catalog

    monkeypatch.setattr(
        "basis.services.connector.catalog.get_connector_catalog",
        _catalog,
    )
    monkeypatch.setattr(
        "basis.services.connector.vault.auth_vault.get_connector_catalog",
        _catalog,
    )
    monkeypatch.setattr(
        "basis.services.connector.runtime.get_connector_catalog",
        _catalog,
    )


def _setup_workspace_db(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "basis_phase2.db"
    conn = sqlite3.connect(str(db))
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
    conn.commit()
    return conn


def test_vault_encryption_and_connection_crud(tmp_path: Path) -> None:
    raw = {"api_key": "pat_secret_123", "nested": {"refresh_token": "rt_456"}}
    ciphertext = encrypt_vault_payload(raw, secret="test-vault-secret")
    assert ciphertext.startswith("v1:")
    assert "pat_secret_123" not in ciphertext
    decrypted = decrypt_vault_payload(ciphertext, secret="test-vault-secret")
    assert decrypted == raw

    conn = _setup_workspace_db(tmp_path)
    try:
        vault = ConnectorAuthVault(conn, vault_secret="test-vault-secret")
        stored = vault.upsert_connection(
            "kb1",
            "airtable",
            auth_type="api_key",
            connection_config={"base_id": "app123"},
            credentials={"api_key": "pat_xyz"},
        )
        assert stored.revision == 1
        assert stored.credentials["api_key"] == "pat_xyz"
        pub = stored.to_public_dict()
        assert "credentials" not in pub
        assert pub["has_credentials"] is True

        # Update increments revision and merges credentials
        updated = vault.upsert_connection(
            "kb1",
            "airtable",
            auth_type="api_key",
            account_profile={"account_id": "usr_99", "display_name": "ops@acme.com"},
        )
        assert updated.revision == 2
        assert updated.credentials["api_key"] == "pat_xyz"
        assert updated.account_profile["account_id"] == "usr_99"

        # OAuth2 authorize URL builder
        vault.upsert_oauth_config(
            "kb1",
            "airtable",
            client_id="cid_airtable",
            client_secret="csec_airtable",
            redirect_uri="https://basis.local/oauth/callback",
        )
        auth_url = vault.build_oauth2_authorize_url(
            "kb1",
            "airtable",
            state="st_001",
            code_challenge="pkce_ch_123",
        )
        assert auth_url.startswith("https://airtable.com/oauth2/v1/authorize?")
        assert "client_id=cid_airtable" in auth_url
        assert "code_challenge=pkce_ch_123" in auth_url
        assert "code_challenge_method=S256" in auth_url
    finally:
        conn.close()


def test_sql_adapter_via_connector_runtime(tmp_path: Path) -> None:
    # Create an external SQLite database acting as the remote ERP database
    ext_db_path = tmp_path / "external_erp.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    annual_revenue REAL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        ext_conn.execute(
            text(
                """
                INSERT INTO customers (customer_id, company_name, tier, annual_revenue, updated_at)
                VALUES
                    ('c1', 'Alpha Inc', 'silver', 100000.0, '2026-01-01T00:00:00Z'),
                    ('c2', 'Beta LLC', 'gold', 250000.0, '2026-01-02T00:00:00Z'),
                    ('c3', 'Gamma Corp', 'platinum', 900000.0, '2026-01-03T00:00:00Z')
                """
            )
        )
    ext_engine.dispose()

    conn = _setup_workspace_db(tmp_path)
    try:
        runtime = ConnectorRuntime(conn, vault_secret="test-secret")
        runtime.vault.upsert_connection(
            "kb1",
            "postgres",
            auth_type="database_dsn",
            connection_config={"dsn": f"sqlite:///{ext_db_path}"},
            credentials={"username": "readonly", "password": "pw"},
        )

        # 1. CHECK
        chk = runtime.check_connection("kb1", "postgres")
        assert chk["ok"] is True
        assert chk["dialect"] == "sqlite"

        # 2. DISCOVER
        schema = runtime.discover_schema(
            "kb1",
            "postgres",
            external_table="customers",
        )
        assert schema.primary_key == ["customer_id"]
        col_types = {f.name: f.data_type for f in schema.fields}
        assert col_types["customer_id"] == "string"
        assert col_types["annual_revenue"] == "number"

        # 3. READ (with incremental cursor watermark)
        read_res = runtime.read_stream(
            "kb1",
            "postgres",
            external_table="customers",
            primary_key_column="customer_id",
            cursor_column="updated_at",
            cursor_watermark="2026-01-02T00:00:00Z",
        )
        assert [r["customer_id"] for r in read_res.records] == ["c2", "c3"]
        assert read_res.next_cursor_value == "2026-01-03T00:00:00Z"

        # 4. MUTATE (update tier and revenue on c1)
        updated_row = runtime.mutate_stream(
            "kb1",
            "postgres",
            external_table="customers",
            operation="update",
            primary_key_column="customer_id",
            external_pk="c1",
            changes={"tier": "gold", "annual_revenue": 180000.0},
        )
        assert updated_row["tier"] == "gold"
        assert updated_row["annual_revenue"] == 180000.0

        # Verify audit runs were recorded
        runs = conn.execute(
            "SELECT operation_kind, ok FROM connector_runs WHERE workspace_id = 'kb1' ORDER BY started_at"
        ).fetchall()
        assert [r[0] for r in runs] == ["check", "read_stream", "mutate_update"]
        assert all(r[1] == 1 for r in runs)
    finally:
        conn.close()


def test_rest_declarative_adapter_airtable_flow(tmp_path: Path) -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        path = request.url.path
        if path == "/v0/meta/whoami":
            return httpx.Response(200, json={"id": "usr_air_1", "email": "dev@acme.com"})
        if path == "/v0/meta/bases/appBase1/tables":
            return httpx.Response(
                200,
                json={
                    "tables": [
                        {
                            "id": "tblCust",
                            "name": "Customers",
                            "fields": [
                                {"name": "Company", "type": "singleLineText"},
                                {"name": "ARR", "type": "currency"},
                                {"name": "Active", "type": "checkbox"},
                            ],
                        }
                    ]
                },
            )
        if path == "/v0/appBase1/tblCust" and request.method == "GET":
            offset = request.url.params.get("offset")
            if not offset:
                return httpx.Response(
                    200,
                    json={
                        "records": [
                            {
                                "id": "rec_1",
                                "createdTime": "2026-01-01T00:00:00Z",
                                "fields": {"Company": "Acme", "ARR": 50000, "Active": True},
                            }
                        ],
                        "offset": "page_token_2",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "id": "rec_2",
                            "createdTime": "2026-01-02T00:00:00Z",
                            "fields": {"Company": "Beta", "ARR": 75000, "Active": False},
                        }
                    ]
                },
            )
        if path == "/v0/appBase1/tblCust/rec_1" and request.method == "PATCH":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": "rec_1", "fields": body.get("fields", {})},
            )
        return httpx.Response(404, json={"error": "not_found"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    conn = _setup_workspace_db(tmp_path)
    try:
        runtime = ConnectorRuntime(
            conn, vault_secret="test-secret", http_client=mock_client
        )
        runtime.vault.upsert_connection(
            "kb1",
            "airtable",
            auth_type="api_key",
            credentials={"api_key": "pat_airtable_secret"},
        )

        # 1. CHECK
        chk = runtime.check_connection("kb1", "airtable")
        assert chk["account_id"] == "usr_air_1"
        assert chk["display_name"] == "dev@acme.com"
        assert captured_requests[0].headers.get("Authorization") == "Bearer pat_airtable_secret"

        # 2. DISCOVER dynamic schema
        disc = runtime.discover_schema(
            "kb1",
            "airtable",
            stream_name="records",
            stream_params={"base_id": "appBase1", "table_id": "tblCust"},
        )
        field_map = {f.name: f.data_type for f in disc.fields}
        assert field_map == {
            "id": "string",
            "Company": "string",
            "ARR": "number",
            "Active": "boolean",
        }

        # 3. READ with automatic cursor pagination & fields unwrap
        read_res = runtime.read_stream(
            "kb1",
            "airtable",
            stream_name="records",
            stream_params={"base_id": "appBase1", "table_id": "tblCust"},
        )
        assert len(read_res.records) == 2
        assert read_res.records[0]["id"] == "rec_1"
        assert read_res.records[0]["Company"] == "Acme"
        assert read_res.records[1]["id"] == "rec_2"
        assert read_res.records[1]["ARR"] == 75000
        assert read_res.next_cursor_value == "2026-01-02T00:00:00Z"

        # 4. MUTATE
        mut_res = runtime.mutate_stream(
            "kb1",
            "airtable",
            stream_name="records",
            operation="update",
            external_pk="rec_1",
            changes={"ARR": 65000},
            stream_params={"base_id": "appBase1", "table_id": "tblCust"},
        )
        assert mut_res["fields"] == {"ARR": 65000}

        # Policy enforcement check
        runtime.vault.upsert_policy("kb1", allowed_providers=["postgres"])
        with pytest.raises(PermissionError, match="blocked by workspace connector policy"):
            runtime.check_connection("kb1", "airtable")
    finally:
        mock_client.close()
        conn.close()


def test_oauth2_code_exchange_and_tool_execution(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth/access_token" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "access_token": "gho_exchanged_token_999",
                    "token_type": "bearer",
                    "scope": "repo,read:user",
                },
            )
        if request.url.path.startswith("/"):
            return httpx.Response(
                200,
                json={
                    "executed_path": request.url.path,
                    "auth": request.headers.get("Authorization"),
                },
            )
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    conn = _setup_workspace_db(tmp_path)
    try:
        runtime = ConnectorRuntime(
            conn, vault_secret="test-secret", http_client=mock_client
        )
        runtime.vault.upsert_oauth_config(
            "kb1",
            "github",
            client_id="gh_cid",
            client_secret="gh_csec",
            redirect_uri="https://app.local/cb",
        )
        stored = runtime.vault.exchange_oauth2_code(
            "kb1",
            "github",
            code="auth_code_abc",
            code_verifier="pkce_verifier_test",
            http_client=mock_client,
        )
        assert stored.credentials["access_token"] == "gho_exchanged_token_999"

        chk = runtime.check_connection("kb1", "github")
        assert chk.get("ok") is True
    finally:
        mock_client.close()
        conn.close()
