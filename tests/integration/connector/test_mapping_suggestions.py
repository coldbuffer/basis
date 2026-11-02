"""Unit and HTTP tests for connector mapping suggestions."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from basis.app import create_app
from basis.services.knowledge.services.mapping_suggestions import (
    column_mappings_from_fields,
    entity_group_key,
    suggest_table_mapping_drafts,
    target_class_uri_for_stream,
)
from basis.infra.runtime.config import Settings


def test_entity_group_and_class_uri_heuristics() -> None:
    assert entity_group_key("members") == "users"
    assert entity_group_key("repositories") == "repositories"
    assert target_class_uri_for_stream("repositories") == "urn:basis:class:Repositories"
    assert target_class_uri_for_stream("table_records", "public.accounts") == (
        "urn:basis:class:Accounts"
    )


def test_column_mappings_from_fields_skips_pk() -> None:
    cols = column_mappings_from_fields(["id", "name", "status"], pk="id")
    assert [c.column for c in cols] == ["name", "status"]
    assert cols[0].predicate_uri == "urn:basis:prop:name"


def test_suggest_http_with_sql_table(tmp_path: Path) -> None:
    ext_db_path = tmp_path / "erp.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
    ext_engine.dispose()

    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db_path}"},
            "credentials": {"username": "u", "password": "p"},
        },
    )

    suggest = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/suggest",
        headers=headers,
        json={
            "sql_tables": [
                {
                    "provider": "postgres",
                                        "stream_name": "table_records",
                    "external_table": "customers",
                }
            ]
        },
    )
    assert suggest.status_code == 200
    data = suggest.json()
    assert len(data["groups"]) == 1
    draft = data["groups"][0]["drafts"][0]["draft"]
    assert draft["primary_key_column"] == "customer_id"
    assert draft["target_class_uri"] == "urn:basis:class:Customers"

    batch = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/batch-create",
        headers=headers,
        json={"mappings": [draft], "run_sync": True},
    )
    assert batch.status_code == 200
    assert len(batch.json()["mappings"]) == 1
    assert batch.json()["sync_results"]


def test_suggest_http_auto_lists_sql_tables_without_sql_tables_body(tmp_path: Path) -> None:
    ext_db_path = tmp_path / "erp_auto.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL
                )
                """
            )
        )
    ext_engine.dispose()

    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data_auto")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "auto@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db_path}"},
            "credentials": {"username": "u", "password": "p"},
        },
    )

    suggest = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/suggest",
        headers=headers,
        json={},
    )
    assert suggest.status_code == 200
    data = suggest.json()
    assert data["groups"], data
    draft = data["groups"][0]["drafts"][0]["draft"]
    assert draft["external_table"] == "customers"


def test_suggest_http_auto_expand_scoped_to_connection(tmp_path: Path) -> None:
    ext_db_path = tmp_path / "erp_scoped.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL
                )
                """
            )
        )
    ext_engine.dispose()

    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data_scoped")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "scoped@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db_path}"},
            "credentials": {"username": "u", "password": "p"},
        },
    )

    scoped = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/suggest",
        headers=headers,
        json={"connections": [{"provider": "postgres"}]},
    )
    assert scoped.status_code == 200
    assert scoped.json()["groups"]

    missing = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/suggest",
        headers=headers,
        json={"connections": [{"provider": "github"}]},
    )
    assert missing.status_code == 200
    assert missing.json()["groups"] == []
