"""Direct rdf:type assignment (MCP) and neighbors."""

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
        json={"email": "etype@example.com", "password": "password1", "display_name": "E"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _mcp(client: TestClient, workspace_id: str, headers: dict, name: str, args: dict) -> dict:
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is False, body["result"].get("content")
    return json.loads(body["result"]["content"][0]["text"])


def test_assign_entity_types_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    subject = "urn:trellis:Artifact:demo1"
    class_uri = "urn:trellis:Artifact"
    out = _mcp(
        client,
        workspace_id,
        headers,
        "assign_entity_types",
        {"assignments": [{"subject_id": subject, "class_uri": class_uri}]},
    )
    assert out.get("created") == 1

    neighbors = _mcp(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "neighbors", "node_id": subject, "depth": 1},
    )
    assert any(
        n.get("relationship") == "type" or n.get("id") == class_uri
        for n in neighbors.get("neighbors") or []
    )


def test_clear_entity_types_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    subject = "urn:trellis:Artifact:clear-demo"
    class_uri = "urn:trellis:Artifact"
    _mcp(
        client,
        workspace_id,
        headers,
        "assign_entity_types",
        {"assignments": [{"subject_id": subject, "class_uri": class_uri}]},
    )
    cleared = _mcp(
        client,
        workspace_id,
        headers,
        "clear_entity_types",
        {"subject_ids": [subject]},
    )
    assert cleared.get("invalidated", 0) >= 1

    facts = _mcp(client, workspace_id, headers, "list_typed_facts", {"limit": 200})
    active = [
        f
        for f in facts.get("facts") or []
        if f.get("subject_id") == subject and f.get("invalidated_at") is None
    ]
    assert not active


def test_propose_mapping_direct_class_via_subject_id(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    subject = "urn:trellis:Document:demo2"
    class_uri = "urn:trellis:Document"
    out = _mcp(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "subject_id": subject,
            "target_kind": "class",
            "target_uri": class_uri,
        },
    )
    assert out.get("assignment", {}).get("created") == 1
