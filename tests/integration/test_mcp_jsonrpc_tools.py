"""Workspace MCP HTTP and API tokens."""

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings

_LOOP_MARKER = "MCP_GRAPH_LOOP_UNIQUE_2010"


def _mcp_tool_json(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    name: str,
    arguments: dict,
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
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["isError"] is False, body["result"].get("content")
    return json.loads(body["result"]["content"][0]["text"])


def test_mcp_basic_graph_closed_loop(tmp_path) -> None:
    """Read corpus → propose fact → review → approve → read back via ledger facts."""
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "loop@example.com", "password": "password1", "display_name": "Loop"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "loop-doc",
            "text": "The capital of France is Paris.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )

    search = _mcp_tool_json(
        client, workspace_id, headers, "search_chunks", {"query": "Paris"}, rpc_id=1
    )
    assert any("Paris" in (c.get("text") or "") for c in search.get("chunks", []))

    proposed = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "propose_remember",
        {"content": f"Acme Corp {_LOOP_MARKER}."},
        rpc_id=2,
    )
    review_item_id = proposed["review_item_id"]

    item = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "get_review_item",
        {"item_id": review_item_id},
        rpc_id=3,
    )
    assert item["item"]["status"] == "open"

    approved = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "approve_review_item",
        {"item_id": review_item_id},
        rpc_id=4,
    )
    assert approved["item"]["status"] == "approved"

    entities = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "entities", "query": "Agent memory"},
        rpc_id=5,
    )
    ledger = entities.get("ledger_entities") or []
    assert ledger, "remember anchor entity should exist"
    entity_id = ledger[0]["id"]

    facts = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "entity_facts",
        {"entity_id": entity_id},
        rpc_id=6,
    )
    assert any(_LOOP_MARKER in str(f.get("object_value") or "") for f in facts.get("facts", []))


def test_mcp_tools_with_api_token(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "mcp@example.com", "password": "password1", "display_name": "M"},
    ).json()
    session_headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session_headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=session_headers,
        json={
            "doc_id": "mcp-doc",
            "text": "The capital of France is Paris. Paris is a city.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session_headers,
        json={"name": "agent", "scope": "read"},
    )
    assert created.status_code == 200
    secret = created.json()["secret"]
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/tokens", headers=session_headers).json()
    assert listed["tokens"][0].get("secret") == secret
    api_headers = {"Authorization": f"Bearer {secret}"}

    info = client.get(f"/api/v1/workspaces/{workspace_id}/mcp", headers=api_headers)
    assert info.status_code == 200
    info_body = info.json()
    assert info_body["mcp_url"].endswith(f"/api/v1/workspaces/{workspace_id}/mcp")
    assert "basis-workspace" in info_body["cursor_example"]["mcpServers"]

    init = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert init.status_code == 200
    assert init.json()["result"]["serverInfo"]["name"] == "basis-workspace-mcp"

    tools = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ).json()
    names = {t["name"] for t in tools["result"]["tools"]}
    assert "search_chunks" in names
    assert "propose_remember" in names
    assert "query_graph" in names
    assert "get_graph_summary" in names
    assert "list_review_items" in names
    assert "list_derived_facts" in names
    assert "list_typed_facts" in names
    assert "list_rules" in names
    assert "get_rule" in names
    assert "list_mappings" in names
    from tests.contract.test_contract_mcp_ledger_ontology_schemas import (
        LEDGER_MAPPING_TOOLS,
        ONTOLOGY_HUB_TOOLS,
    )

    for tool_name in {**LEDGER_MAPPING_TOOLS, **ONTOLOGY_HUB_TOOLS}:
        assert tool_name in names
    assert "get_statement" in names
    assert "run_reasoning" in names
    assert "approve_review_item" in names
    assert "approve_review_item" in names
    assert "reject_review_item" in names
    assert "list_processing_jobs" in names

    search = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "search_chunks", "arguments": {"query": "Paris"}},
        },
    ).json()
    assert search["result"]["isError"] is False
    assert "Paris" in search["result"]["content"][0]["text"]

    wrong_workspace = client.post(
        "/api/v1/workspaces/00000000-0000-0000-0000-000000000000/mcp",
        headers=api_headers,
        json={"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {}},
    )
    assert wrong_workspace.status_code == 403

    remember = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=session_headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "propose_remember",
                "arguments": {"content": "MCP remembered fact for review."},
            },
        },
    )
    assert remember.status_code == 200
    remember_payload = json.loads(remember.json()["result"]["content"][0]["text"])
    review_item_id = remember_payload.get("review_item_id")
    assert review_item_id

    listed = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=session_headers,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "list_review_items",
                "arguments": {"kind": "statement_remember", "status": "open"},
            },
        },
    ).json()
    list_payload = json.loads(listed["result"]["content"][0]["text"])
    assert any(i["id"] == review_item_id for i in list_payload["items"])

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=session_headers,
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "approve_review_item",
                "arguments": {"item_id": review_item_id, "rationale": "looks good"},
            },
        },
    ).json()
    assert approved["result"]["isError"] is False
    approve_payload = json.loads(approved["result"]["content"][0]["text"])
    assert approve_payload["item"]["status"] == "approved"
    assert approve_payload.get("decision_id")


def test_mcp_reject_review_item_entity_merge(tmp_path) -> None:
    """MCP reject_review_item matches HTTP reject for entity_merge proposals."""
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "mcp-rej@example.com", "password": "password1", "display_name": "McpRej"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/entity-merge",
        headers=headers,
        json={"primary_id": "node-a", "duplicate_ids": ["node-b"]},
    )
    assert proposed.status_code == 200
    item_id = proposed.json()["item"]["id"]

    rejected = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "reject_review_item",
        {"item_id": item_id, "rationale": "not duplicates"},
        rpc_id=1,
    )
    assert rejected["item"]["status"] == "rejected"


def test_mcp_busy_when_semaphore_saturated(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, mcp_max_inflight=0)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "busy@example.com", "password": "password1", "display_name": "Busy"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "mcp_busy"


def test_mcp_timeout(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, mcp_timeout_seconds=1)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "to@example.com", "password": "password1", "display_name": "To"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    def slow_batch(*_args, **_kwargs):
        time.sleep(2)
        return {"jsonrpc": "2.0", "id": 1, "result": {}}

    with patch("basis.interface.http.workspace.mcp.mcp_http.handle_batch", side_effect=slow_batch):
        resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
        )
    assert resp.status_code == 504
    assert resp.json()["detail"]["code"] == "mcp_timeout"


def test_mcp_resources(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "res@example.com", "password": "password1", "display_name": "Res"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "alias-doc",
            "text": "The capital of France is Paris.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )

    init = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    ).json()
    assert "resources" in init["result"]["capabilities"]

    discovery = client.get(f"/api/v1/workspaces/{workspace_id}/mcp", headers=headers).json()
    assert "semantica://graph/summary" in discovery["resources"]

    listed = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}},
    ).json()
    uris = {r["uri"] for r in listed["result"]["resources"]}
    assert "semantica://schema/info" in uris
    assert "semantica://guide/evidence" in uris

    schema_read = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 25,
            "method": "resources/read",
            "params": {"uri": "semantica://schema/info"},
        },
    ).json()
    schema_payload = json.loads(schema_read["result"]["contents"][0]["text"])
    assert schema_payload.get("evidence_guide", {}).get("version") == 1
    assert "propose_remember" in str(schema_payload.get("evidence_guide", {}))

    read = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": "semantica://graph/summary"},
        },
    ).json()
    summary = json.loads(read["result"]["contents"][0]["text"])
    assert summary.get("graph_ready") is True
    assert summary.get("workspace_id") == workspace_id
