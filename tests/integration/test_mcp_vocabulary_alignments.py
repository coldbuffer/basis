"""MCP vocabulary alignment write tools parity with HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app

pytest.importorskip("semantica")


def _client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "mcpali@example.com", "password": "password1", "display_name": "M"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _mcp(
    client: TestClient,
    workspace_id: str,
    headers: dict,
    name: str,
    args: dict,
    *,
    rpc_id: int,
) -> dict:
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
    assert body["result"]["isError"] is False, (name, body["result"].get("content"))
    return json.loads(body["result"]["content"][0]["text"])


def test_mcp_upsert_list_delete_vocabulary_alignment(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client, workspace_id, headers = _client(tmp_path)
    payload = _mcp(
        client,
        workspace_id,
        headers,
        "upsert_vocabulary_alignment",
        {
            "source_uri": "http://example.org/a#Class1",
            "target_uri": "http://example.org/b#Class2",
            "relation": "skos:exactMatch",
            "confidence": 0.88,
        },
        rpc_id=1,
    )
    alignment_id = payload["alignment"]["id"]

    listed = _mcp(
        client,
        workspace_id,
        headers,
        "list_vocabulary_alignments",
        {},
        rpc_id=2,
    )
    assert len(listed["alignments"]) == 1
    assert listed["alignments"][0]["id"] == alignment_id

    removed = _mcp(
        client,
        workspace_id,
        headers,
        "delete_vocabulary_alignment",
        {"alignment_id": alignment_id},
        rpc_id=3,
    )
    assert removed["status"] == "removed"

    listed_after = _mcp(
        client,
        workspace_id,
        headers,
        "list_vocabulary_alignments",
        {},
        rpc_id=4,
    )
    assert listed_after["alignments"] == []


def test_mcp_suggest_vocabulary_alignments_on_empty_graph(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client, workspace_id, headers = _client(tmp_path)
    payload = _mcp(
        client,
        workspace_id,
        headers,
        "suggest_vocabulary_alignments",
        {"threshold": 0.5, "limit": 5},
        rpc_id=10,
    )
    assert isinstance(payload.get("suggestions"), list)
