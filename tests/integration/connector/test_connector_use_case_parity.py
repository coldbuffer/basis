"""HTTP connector routes share application use cases with MCP operations."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

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


def _http_manifest_auth_modes(row: dict) -> list[str]:
    return [
        entry["auth_mode"]
        for entry in (row.get("auth") or [])
        if isinstance(entry, dict) and entry.get("auth_mode")
    ]


def _auth_client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "parity")))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "parity@basis.local", "password": "password123", "display_name": "P"},
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def test_upsert_and_delete_connection_http_matches_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    payload = {
        "service": "postgres",
                "connection_scope": "workspace",
        "auth_type": "custom",
        "connection_config": {"host": "localhost", "database": "db"},
        "credentials": {"password": "secret"},
    }
    http_put = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "connection_scope": payload["connection_scope"],
            "auth_type": payload["auth_type"],
            "connection_config": payload["connection_config"],
            "credentials": payload["credentials"],
        },
    )
    assert http_put.status_code == 200

    mcp_put = _mcp_call(client, workspace_id, headers, "upsert_connector_connection", payload)
    assert mcp_put["connection"]["service"] == "postgres"
    assert http_put.json()["connection"]["service"] == mcp_put["connection"]["service"]

    mcp_del = _mcp_call(
        client,
        workspace_id,
        headers,
        "delete_connector_connection",
        {
            "service": "postgres",
                        "connection_scope": "workspace",
        },
    )
    assert mcp_del == {"deleted": True}
    http_del = client.delete(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
    )
    assert http_del.status_code == 404


def test_check_connection_http_matches_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    ext_db = tmp_path / "check-remote.db"
    body = {
        "connection_scope": "workspace",
        "auth_type": "database_dsn",
        "connection_config": {"dsn": f"sqlite:///{ext_db}"},
        "credentials": {},
    }
    assert (
        client.put(
            f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
            headers=headers,
            json=body,
        ).status_code
        == 200
    )
    mcp_check = _mcp_call(
        client,
        workspace_id,
        headers,
        "check_connector_connection",
        {
            "service": "postgres",
                        "connection_scope": "workspace",
        },
    )
    http_check = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres/check",
        headers=headers,
    )
    assert http_check.status_code == 200
    assert mcp_check["ok"] is True
    assert mcp_check.get("profile") == http_check.json().get("profile")


def test_list_connections_http_matches_mcp_op(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    put = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "connection_scope": "workspace",
            "auth_type": "custom",
            "connection_config": {"host": "localhost", "database": "db"},
            "credentials": {"password": "secret"},
        },
    )
    assert put.status_code == 200

    mcp_list = _mcp_call(
        client, workspace_id, headers, "list_connector_connections", {}
    )
    http_list = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections",
        headers=headers,
    )
    assert http_list.status_code == 200

    mcp_keys = {c["service"] for c in mcp_list["connections"]}
    http_keys = {c["service"] for c in http_list.json()["connections"]}
    assert mcp_keys == http_keys
    assert "postgres" in mcp_keys

    http_by_key = {c["service"]: c for c in http_list.json()["connections"]}
    for row in mcp_list["connections"]:
        http_row = http_by_key[row["service"]]
        assert set(row.keys()) <= set(http_row.keys())
        for key, value in row.items():
            assert http_row[key] == value


def test_list_catalog_services_http_matches_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    params = {"has_streams_only": True, "limit": 25}
    mcp_list = _mcp_call(
        client,
        workspace_id,
        headers,
        "list_connector_catalog",
        params,
    )
    http_list = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog",
        headers=headers,
        params=params,
    )
    assert http_list.status_code == 200
    mcp_services = {c["service"] for c in mcp_list["connectors"]}
    http_services = {c["service"] for c in http_list.json()["connectors"]}
    assert mcp_services == http_services
    assert "postgres" in mcp_services
    http_by_service = {c["service"]: c for c in http_list.json()["connectors"]}
    for mcp_row in mcp_list["connectors"]:
        http_row = http_by_service[mcp_row["service"]]
        for key in ("service", "display_name", "description", "categories"):
            assert mcp_row[key] == http_row[key]
        assert mcp_row["auth_modes"] == _http_manifest_auth_modes(http_row)


def test_describe_connector_service_http_matches_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    service = "postgres"
    mcp_detail = _mcp_call(
        client,
        workspace_id,
        headers,
        "describe_connector_service",
        {"service": service},
    )
    http_detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog/{service}",
        headers=headers,
    )
    assert http_detail.status_code == 200
    http_conn = http_detail.json()["connector"]
    mcp_conn = mcp_detail["connector"]
    for key in ("service", "display_name", "description", "categories"):
        assert mcp_conn[key] == http_conn[key]
    assert mcp_conn["auth_modes"] == _http_manifest_auth_modes(http_conn)
    assert mcp_conn["stream_count"] >= 1
    assert len(mcp_conn.get("streams") or []) >= 1
    # Full HTTP manifest may omit or reshape top-level streams[] while MCP exposes slices.


def _mcp_mapping_slice(row: dict) -> tuple:
    return (
        row["id"],
        row["provider"],
        row["stream_name"],
        row["external_table"],
        row["sync_direction"],
        row["writeback_mode"],
        row["status"],
    )


def test_list_table_mappings_http_matches_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    mcp_empty = _mcp_call(
        client, workspace_id, headers, "list_connector_table_mappings", {"limit": 50}
    )
    http_empty = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
    )
    assert http_empty.status_code == 200
    assert mcp_empty["mappings"] == []
    assert http_empty.json()["mappings"] == []

    ext_db = tmp_path / "parity-remote.db"
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
    map_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
        json={
            "provider": "postgres",
                        "stream_name": "table_records",
            "external_table": "parity_items",
            "primary_key_column": "id",
            "cursor_column": "updated_at",
            "label_column": "name",
            "target_class_uri": "urn:basis:class:ParityItem",
            "column_mappings": [],
            "sync_direction": "inbound",
            "writeback_mode": "disabled",
        },
    )
    assert map_resp.status_code == 200
    mapping_id = map_resp.json()["mapping"]["id"]

    mcp_list = _mcp_call(
        client, workspace_id, headers, "list_connector_table_mappings", {"limit": 200}
    )
    http_list = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
    )
    assert http_list.status_code == 200
    mcp_by_id = {m["id"]: m for m in mcp_list["mappings"]}
    http_rows = http_list.json()["mappings"]
    assert set(mcp_by_id) == {r["id"] for r in http_rows}
    assert mapping_id in mcp_by_id
    for row in http_rows:
        mcp_row = mcp_by_id[row["id"]]
        assert _mcp_mapping_slice(mcp_row) == _mcp_mapping_slice(
            {
                "id": row["id"],
                "provider": row["provider"],
                                "stream_name": row["stream_name"],
                "external_table": row["external_table"],
                "sync_direction": row["sync_direction"],
                "writeback_mode": row["writeback_mode"],
                "status": row["status"],
            }
        )
        assert set(mcp_row.keys()) <= set(row.keys())
        for key, value in mcp_row.items():
            assert row[key] == value
