"""Static MCP catalog is wired consistently across capabilities, discovery, and tools/list."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from basis.application.tool_catalog import TOOL_NAMES
from basis.application.tool_catalog.catalog import OPERATIONS
from basis.interface.http.app import create_app
from basis.interface.mcp.dispatch import get_static_tool_definitions
from basis.infra.runtime.config import Settings


def test_static_tool_definitions_match_tool_names() -> None:
    names = [t["name"] for t in get_static_tool_definitions()]
    assert names == list(TOOL_NAMES)
    assert len(names) == len(TOOL_NAMES)


def test_get_capabilities_mcp_tools_match_catalog(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "cap@example.com", "password": "password1", "display_name": "C"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    caps = client.get(
        f"/api/v1/workspaces/{workspace_id}/capabilities",
        headers=headers,
    )
    assert caps.status_code == 200
    assert caps.json()["mcp_tools"] == list(TOOL_NAMES)


def test_mcp_discovery_and_jsonrpc_list_include_static_catalog(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "list@example.com", "password": "password1", "display_name": "L"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    discovery = client.get(f"/api/v1/workspaces/{workspace_id}/mcp", headers=headers)
    assert discovery.status_code == 200
    body = discovery.json()
    assert body["static_tools"] == list(TOOL_NAMES)
    assert set(TOOL_NAMES).issubset(set(body["tools"]))

    rpc = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert rpc.status_code == 200
    tools = rpc.json()["result"]["tools"]
    by_name = {t["name"]: t for t in tools}
    for name in TOOL_NAMES:
        assert name in by_name
        assert by_name[name]["description"]
        assert by_name[name]["inputSchema"]["type"] == "object"

    call = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_graph_summary", "arguments": {}},
        },
    )
    assert call.status_code == 200
    payload = json.loads(call.json()["result"]["content"][0]["text"])
    assert payload["workspace_id"] == workspace_id
