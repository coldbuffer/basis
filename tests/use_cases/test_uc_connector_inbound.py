"""Connector inbound journey: external DB → mapping → sync → ledger/graph."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.app import create_app


def test_uc_connector_postgres_sqlite_inbound_sync(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    ext_db = tmp_path / "external_customers.db"
    engine = create_engine(f"sqlite:///{ext_db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO customers (id, name, updated_at)
                VALUES ('c1', 'Inbound UC Corp', '2026-03-01T00:00:00Z')
                """
            )
        )
    engine.dispose()

    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data", ingest_inline=True)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "uc-inbound@basis.local", "password": "password1", "display_name": "UC"},
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    put_conn = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db}"},
            "credentials": {},
        },
    )
    assert put_conn.status_code == 200

    check = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres/check",
        headers=headers,
    )
    assert check.status_code == 200
    assert check.json()["ok"] is True

    mapping = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
        json={
            "provider": "postgres",
            "stream_name": "table_records",
            "external_table": "customers",
            "primary_key_column": "id",
            "cursor_column": "updated_at",
            "label_column": "name",
            "target_class_uri": "urn:basis:class:UcCustomer",
            "column_mappings": [],
            "sync_direction": "inbound",
        },
    )
    assert mapping.status_code == 200
    mapping_id = mapping.json()["mapping"]["id"]

    synced = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}/sync",
        headers=headers,
    )
    assert synced.status_code == 200
    assert synced.json().get("added", 0) >= 1

    nodes = client.get(f"/api/v1/workspaces/{workspace_id}/graph/nodes", headers=headers)
    assert nodes.status_code == 200
    labels = {
        n.get("label") or (n.get("properties") or {}).get("name") for n in nodes.json().get("nodes", [])
    }
    assert "Inbound UC Corp" in labels

    runs = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/runs",
        headers=headers,
        params={"limit": 10},
    )
    assert runs.status_code == 200
    assert runs.json().get("runs")
