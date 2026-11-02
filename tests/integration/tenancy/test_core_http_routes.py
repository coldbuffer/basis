"""HTTP routes delegate MCP-aligned operations to basis.application.run."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _session_client(tmp_path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "core-http@example.com", "password": "password1", "display_name": "C"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "core-http-doc",
            "text": "Vienna is the capital of Austria.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )
    return client, workspace_id, headers


def test_search_and_chunk_via_core(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "Vienna", "limit": 5},
    )
    assert search.status_code == 200
    body = search.json()
    assert "chunks" in body or "hits" in body or body.get("query")

    mcp = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_chunks", "arguments": {"query": "Vienna", "limit": 5}},
        },
    ).json()
    assert mcp["result"]["isError"] is False


def test_find_entities_and_describe_workspace_via_core(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    workspace_detail = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers).json()
    assert workspace_detail.get("document_count", 0) >= 1
    assert "chunk_count" in workspace_detail

    found = client.get(
        f"/api/v1/workspaces/{workspace_id}/entities/find",
        headers=headers,
        params={"q": "Vienna", "limit": 5},
    )
    assert found.status_code == 200
    body = found.json()
    assert body.get("query") == "Vienna"
    assert "ledger_entities" in body

    caps = client.get(f"/api/v1/workspaces/{workspace_id}/capabilities", headers=headers).json()
    assert "search_chunks" in caps.get("mcp_tools", [])


def test_graph_search_via_core(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/search",
        headers=headers,
        json={"query": "Vienna", "limit": 5},
    )
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_remember_via_core(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": "Austria uses euros."},
    )
    assert resp.status_code == 200
    assert "statement_id" in resp.json() or "id" in resp.json()
