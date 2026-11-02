"""MCP / integration operations for BOCP connectors."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from basis.infra.runtime.config import Settings
from basis.app import create_app


def _mcp_call(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    name: str,
    arguments: dict,
) -> dict:
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is False, body["result"].get("content")
    return json.loads(body["result"]["content"][0]["text"])


def test_mcp_list_connector_catalog_and_mappings(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "mcp-conn@example.com",
            "password": "password1",
            "display_name": "MCP",
        },
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    catalog = _mcp_call(
        client,
        workspace_id,
        headers,
        "list_connector_catalog",
        {"has_streams_only": True, "limit": 20},
    )
    assert "connectors" in catalog
    services = {c["service"] for c in catalog["connectors"]}
    assert "postgres" in services

    detail = _mcp_call(
        client,
        workspace_id,
        headers,
        "describe_connector_service",
        {"service": "postgres"},
    )
    assert detail["connector"]["service"] == "postgres"
    assert detail["connector"]["stream_count"] >= 1

    mappings = _mcp_call(
        client,
        workspace_id,
        headers,
        "list_connector_table_mappings",
        {"limit": 10},
    )
    assert mappings["mappings"] == []

    blocked = _mcp_call(
        client,
        workspace_id,
        headers,
        "execute_connector_tool",
        {"service": "postgres", "tool_id": "nonexistent_tool"},
    )
    assert "error" in blocked


def test_mcp_sync_connector_table_mapping_inbound(tmp_path: Path) -> None:
    ext_db_path = tmp_path / "remote.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE items (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        ext_conn.execute(
            text(
                "INSERT INTO items (id, name, updated_at) VALUES ('i1', 'One', '2026-01-01T00:00:00Z')"
            )
        )
    ext_engine.dispose()

    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "mcp-sync@example.com",
            "password": "password1",
            "display_name": "MCP Sync",
        },
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    put_conn = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db_path}"},
            "credentials": {},
        },
    )
    assert put_conn.status_code == 200

    map_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
        json={
            "provider": "postgres",
                        "stream_name": "table_records",
            "external_table": "items",
            "primary_key_column": "id",
            "cursor_column": "updated_at",
            "label_column": "name",
            "target_class_uri": "urn:basis:class:Item",
            "column_mappings": [],
            "sync_direction": "inbound",
            "writeback_mode": "disabled",
        },
    )
    assert map_resp.status_code == 200
    mapping_id = map_resp.json()["mapping"]["id"]

    stats = _mcp_call(
        client,
        workspace_id,
        headers,
        "sync_connector_table_mapping",
        {"mapping_id": mapping_id},
    )
    assert stats["added"] == 1
    assert stats["fetched_rows"] == 1

    stats2 = _mcp_call(
        client,
        workspace_id,
        headers,
        "sync_connector_table_mapping",
        {"mapping_id": mapping_id},
    )
    assert stats2["unchanged"] == 1
    assert stats2["updated"] == 0
