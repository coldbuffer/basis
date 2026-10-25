"""Smoke checks: committed OpenAPI documents key integration paths."""

from fastapi.testclient import TestClient

from basis.application.tool_catalog import TOOL_NAMES
from basis.interface.http.app import create_app
from basis.interface.contract.openapi.spec import openapi_v1_full
from basis.infra.runtime.config import Settings

_INTEGRATION_PATHS = (
    "/api/v1/workspaces/{workspace_id}/search",
    "/api/v1/workspaces/{workspace_id}/mcp",
    "/api/v1/workspaces/{workspace_id}/entities/find",
    "/api/v1/workspaces/{workspace_id}/graph/search",
    "/api/v1/workspaces/{workspace_id}/ledger/chunks/{chunk_id}",
    "/openapi/v1.json",
    "/openapi/v1/workspaces.json",
)


def test_openapi_yaml_lists_integration_paths() -> None:
    paths = openapi_v1_full()["paths"]
    for template in _INTEGRATION_PATHS:
        assert template in paths, f"missing path in OpenAPI export: {template}"


def test_v1_integration_endpoints_respond(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "contract@example.com", "password": "password1", "display_name": "C"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    assert client.get("/openapi/v1/workspaces.json").status_code == 200
    assert client.get("/openapi/v1/kb.json").status_code == 404

    doc = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "contract-doc",
            "text": "Berlin is a city in Germany.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )
    assert doc.status_code == 200

    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "Berlin", "limit": 5},
    )
    assert search.status_code == 200

    graph = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/search",
        headers=headers,
        json={"query": "Berlin", "limit": 5},
    )
    assert graph.status_code == 200
    assert "results" in graph.json()

    find = client.get(
        f"/api/v1/workspaces/{workspace_id}/entities/find",
        headers=headers,
        params={"q": "Berlin", "limit": 5},
    )
    assert find.status_code == 200

    mcp = client.get(f"/api/v1/workspaces/{workspace_id}/mcp", headers=headers)
    assert mcp.status_code == 200
    tools = mcp.json().get("tools") or []
    assert set(TOOL_NAMES).issubset(set(tools))
    assert "query_graph" in tools
    assert "search_chunks" in tools
    assert "connector_postgres__table_records__list" in tools
