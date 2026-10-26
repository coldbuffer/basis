"""MCP ledger write tools: invalidate_entities, delete_document."""

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
        json={"email": "ledwrite@example.com", "password": "password1", "display_name": "L"},
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


def test_invalidate_entities_mcp(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    subject = "urn:trellis:Artifact:inv-demo"
    class_uri = "urn:trellis:Artifact"
    _mcp(
        client,
        workspace_id,
        headers,
        "assign_entity_types",
        {"assignments": [{"subject_id": subject, "class_uri": class_uri}]},
    )
    summary_before = _mcp(client, workspace_id, headers, "get_graph_summary", {})
    nodes_before = int(summary_before.get("node_count_active") or summary_before.get("node_count") or 0)

    out = _mcp(
        client,
        workspace_id,
        headers,
        "invalidate_entities",
        {"entity_ids": [subject]},
    )
    assert out.get("invalidated") == 1
    assert out.get("projection") is not None

    summary_after = _mcp(client, workspace_id, headers, "get_graph_summary", {})
    nodes_after = int(summary_after.get("node_count_active") or summary_after.get("node_count") or 0)
    assert nodes_after < nodes_before


def test_delete_document_mcp_by_doc_id(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "mcp-del", "text": "Remove via MCP."},
    )
    assert created.status_code == 200

    out = _mcp(
        client,
        workspace_id,
        headers,
        "delete_document",
        {"document_id": "mcp-del"},
    )
    assert out.get("ok") is True
    assert out.get("doc_id") == "mcp-del"

    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    assert not any(d.get("doc_id") == "mcp-del" for d in docs)


def test_delete_entity_mcp(tmp_path: Path) -> None:
    from basis.domain.knowledge.blob_store import BlobStore
    from basis.domain.knowledge.store import KnowledgeStore

    client, workspace_id, headers = _client(tmp_path)
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    entity_id = store.create_entity(workspace_id, canonical_label="McpDeleteMe")
    store.close()

    out = _mcp(client, workspace_id, headers, "delete_entity", {"entity_id": entity_id})
    assert out.get("ok") is True
    assert out.get("entity_id") == entity_id
