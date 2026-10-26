"""Workspace API token per-operation grants."""

import json

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def test_api_token_allowed_operations_mcp_and_http(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "grants@example.com", "password": "password1", "display_name": "G"},
    ).json()
    session = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session,
        json={
            "name": "search-only",
            "scope": "read",
            "mcp_allowed_operations": ["search_chunks"],
            "http_allowed_operations": ["graph_stats"],
        },
    )
    assert created.status_code == 200
    secret = created.json()["secret"]
    api_headers = {"Authorization": f"Bearer {secret}"}

    allowed_stats = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers)
    assert allowed_stats.status_code == 200

    denied_nodes = client.get(f"/api/v1/workspaces/{workspace_id}/graph/nodes", headers=api_headers)
    assert denied_nodes.status_code == 403

    mcp_list = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert mcp_list.status_code == 200
    tools = mcp_list.json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"search_chunks"}

    denied_call = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_mappings", "arguments": {}},
        },
    )
    assert denied_call.status_code == 200
    payload = json.loads(denied_call.json()["result"]["content"][0]["text"])
    assert payload.get("code") == "forbidden"


def test_api_token_ontology_read_without_write_mcp(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ont-grant@example.com", "password": "password1", "display_name": "OG"},
    ).json()
    session = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session,
        json={
            "name": "ontology-read",
            "scope": "read",
            "mcp_allowed_operations": ["list_ontology_registry", "list_mappings"],
        },
    )
    assert created.status_code == 200
    api_headers = {"Authorization": f"Bearer {created.json()['secret']}"}

    allowed = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_ontology_registry", "arguments": {}},
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["result"]["isError"] is False

    denied = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "propose_mapping", "arguments": {"signature": "surface:x", "status": "proposed"}},
        },
    )
    assert denied.status_code == 200
    payload = json.loads(denied.json()["result"]["content"][0]["text"])
    assert payload.get("code") == "forbidden"


def test_api_token_list_create_and_revoke(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "token-life@example.com", "password": "password1", "display_name": "T"},
    ).json()
    session = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session).json()["workspaces"][0]["id"]

    empty = client.get(f"/api/v1/workspaces/{workspace_id}/tokens", headers=session)
    assert empty.status_code == 200
    assert empty.json()["tokens"] == []

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session,
        json={"name": "revoke-me", "scope": "read"},
    )
    assert created.status_code == 200
    token_id = created.json()["token"]["id"]
    secret = created.json()["secret"]

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/tokens", headers=session).json()["tokens"]
    assert len(listed) == 1
    assert listed[0]["id"] == token_id

    api_headers = {"Authorization": f"Bearer {secret}"}
    assert (
        client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers).status_code == 200
    )

    deleted = client.delete(f"/api/v1/workspaces/{workspace_id}/tokens/{token_id}", headers=session)
    assert deleted.status_code == 200

    assert client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers).status_code == 401


def test_viewer_cannot_manage_workspace_api_tokens(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    owner = client.post(
        "/api/v1/auth/register",
        json={"email": "tok-own@example.com", "password": "password1", "display_name": "Own"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Token ACL KB", "visibility": "restricted"},
    ).json()["id"]

    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": "tok-view@example.com", "password": "password1", "display_name": "View"},
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": viewer["user"]["id"], "role": "viewer"},
    )
    viewer_headers = {"Authorization": f"Bearer {viewer['token']}"}

    assert client.get(f"/api/v1/workspaces/{workspace_id}/tokens", headers=viewer_headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/workspaces/{workspace_id}/tokens",
            headers=viewer_headers,
            json={"name": "nope", "scope": "read"},
        ).status_code
        == 403
    )
