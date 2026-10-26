"""MCP statement-mapping tools vs HTTP."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


def _client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "map-mcp@example.com", "password": "password1", "display_name": "M"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _mcp(client: TestClient, workspace_id: str, headers: dict, name: str, args: dict, rpc_id: int = 1) -> dict:
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is False, body["result"].get("content")
    return json.loads(body["result"]["content"][0]["text"])


def test_list_mappings_mcp_matches_http(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    _mcp(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "signature": "surface:mcp_list_probe",
            "status": "proposed",
            "target_kind": "property",
            "direction": "forward",
        },
        rpc_id=1,
    )
    mcp = _mcp(client, workspace_id, headers, "list_mappings", {"status": "proposed", "limit": 50}, rpc_id=2)
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/mappings",
        headers=headers,
        params={"status": "proposed", "limit": 50},
    )
    assert http.status_code == 200
    assert mcp.get("mappings") == http.json()["mappings"]


def test_list_entity_type_object_labels_mcp_matches_http(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    mcp = _mcp(client, workspace_id, headers, "list_entity_type_object_labels", {"limit": 25})
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entity-type-object-labels",
        headers=headers,
        params={"limit": 25},
    )
    assert http.status_code == 200
    assert mcp.get("labels") == http.json()["labels"]
    assert mcp.get("type_surface_phrases") == http.json()["type_surface_phrases"]


def test_update_mapping_status_confirm_via_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    created = _mcp(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "signature": "surface:confirm_me",
            "status": "proposed",
            "target_kind": "property",
            "direction": "forward",
            "target_uri": "http://example.org/mcpConfirm",
        },
        rpc_id=3,
    )
    mapping_id = created["mapping"]["id"]
    confirmed = _mcp(
        client,
        workspace_id,
        headers,
        "update_mapping_status",
        {"mapping_id": mapping_id, "status": "confirmed"},
        rpc_id=4,
    )
    assert confirmed["mapping"]["status"] == "confirmed"
    http_confirmed = client.post(
        f"/api/v1/workspaces/{workspace_id}/mappings/{mapping_id}/status",
        headers=headers,
        json={"status": "confirmed"},
    )
    assert http_confirmed.status_code == 200
    assert http_confirmed.json()["mapping"]["status"] == "confirmed"
    mcp_list = _mcp(
        client,
        workspace_id,
        headers,
        "list_mappings",
        {"status": "confirmed", "limit": 50},
        rpc_id=5,
    )
    assert any(m["id"] == mapping_id for m in mcp_list.get("mappings") or [])


def test_update_mapping_status_reject_invalidates_mapping(tmp_path: Path) -> None:
    """Rejected mappings are invalidated and omitted from default list (by design)."""
    client, workspace_id, headers = _client(tmp_path)
    created = _mcp(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "signature": "surface:reject_me",
            "status": "proposed",
            "target_kind": "none",
            "direction": "n/a",
        },
        rpc_id=6,
    )
    mapping_id = created["mapping"]["id"]
    rejected = _mcp(
        client,
        workspace_id,
        headers,
        "update_mapping_status",
        {"mapping_id": mapping_id, "status": "rejected", "why": "mcp test"},
        rpc_id=7,
    )
    assert rejected["mapping"]["status"] == "rejected"
    listed = _mcp(client, workspace_id, headers, "list_mappings", {"limit": 50}, rpc_id=8)
    assert not any(m["id"] == mapping_id for m in listed.get("mappings") or [])
