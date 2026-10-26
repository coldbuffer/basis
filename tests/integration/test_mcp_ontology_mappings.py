"""MCP ontology hub and statement-mapping tools vs HTTP parity."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def _auth_client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ont-mcp@example.com", "password": "password1", "display_name": "O"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _mcp_call(
    client: TestClient,
    workspace_id: str,
    headers: dict[str, str],
    name: str,
    arguments: dict,
    *,
    rpc_id: int = 1,
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


def _mapping_slice(row: dict) -> tuple:
    return (
        row["signature"],
        row.get("target_uri"),
        row.get("target_kind"),
        row.get("direction"),
        row["status"],
    )


def test_list_ontology_registry_mcp_matches_http(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    mcp = _mcp_call(client, workspace_id, headers, "list_ontology_registry", {})
    http = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/registry", headers=headers)
    assert http.status_code == 200
    assert mcp.get("registry") == http.json()


def test_propose_mapping_mcp_visible_via_http_list(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    signature = "surface:mcp_parity_probe"
    created = _mcp_call(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "signature": signature,
            "target_kind": "property",
            "direction": "forward",
            "status": "proposed",
            "why": "mcp parity",
        },
        rpc_id=2,
    )
    mapping_id = created["mapping"]["id"]
    listed_http = client.get(
        f"/api/v1/workspaces/{workspace_id}/mappings",
        headers=headers,
        params={"status": "proposed"},
    )
    assert listed_http.status_code == 200
    row_http = next(m for m in listed_http.json()["mappings"] if m["id"] == mapping_id)
    assert _mapping_slice(row_http) == _mapping_slice(created["mapping"])


def test_list_surface_phrases_mcp_matches_http(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    mcp = _mcp_call(client, workspace_id, headers, "list_surface_phrases", {"limit": 50})
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/surface-phrases",
        headers=headers,
        params={"limit": 50},
    )
    assert http.status_code == 200
    assert mcp.get("phrases") == http.json()["phrases"]


def test_get_and_approve_ontology_proposal_mcp(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _auth_client(e2e_dir)
    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    assert seeded.status_code == 200
    proposal_id = seeded.json().get("proposal_id")
    assert isinstance(proposal_id, str) and proposal_id

    mcp_get = _mcp_call(
        client,
        workspace_id,
        headers,
        "get_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=10,
    )
    http_get = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}",
        headers=headers,
    )
    assert http_get.status_code == 200
    assert mcp_get["proposal"] == http_get.json()
    assert mcp_get["proposal"]["state"] == "proposed"

    approved = _mcp_call(
        client,
        workspace_id,
        headers,
        "approve_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=11,
    )
    assert approved.get("status") == "approved"
    assert client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}",
        headers=headers,
    ).json()["state"] == "approved"


def test_publish_ontology_proposal_mcp(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _auth_client(e2e_dir)
    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    proposal_id = seeded.json()["proposal_id"]

    _mcp_call(
        client,
        workspace_id,
        headers,
        "approve_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=20,
    )
    published = _mcp_call(
        client,
        workspace_id,
        headers,
        "publish_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=21,
    )
    assert published.get("status") == "published"
    assert published.get("nodes_added", 0) >= 1

    http_publish = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}/publish",
        headers=headers,
    )
    assert http_publish.status_code == 400

    proposal = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}",
        headers=headers,
    ).json()
    assert proposal["state"] == "published"


def test_list_ontology_drafts_mcp_matches_http(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _auth_client(e2e_dir)
    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    ontology_uri = seeded.json()["ontology_uri"]

    mcp = _mcp_call(
        client,
        workspace_id,
        headers,
        "list_ontology_drafts",
        {"ontology_uri": ontology_uri},
        rpc_id=30,
    )
    encoded_uri = quote(ontology_uri, safe="")
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/drafts/{encoded_uri}",
        headers=headers,
    )
    assert http.status_code == 200
    assert mcp.get("drafts") == http.json()


def test_list_ontology_versions_after_publish_mcp(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _auth_client(e2e_dir)
    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    proposal_id = seeded.json()["proposal_id"]
    ontology_uri = seeded.json()["ontology_uri"]

    _mcp_call(
        client,
        workspace_id,
        headers,
        "approve_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=40,
    )
    _mcp_call(
        client,
        workspace_id,
        headers,
        "publish_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=41,
    )

    mcp_versions = _mcp_call(
        client,
        workspace_id,
        headers,
        "list_ontology_versions",
        {"ontology_uri": ontology_uri},
        rpc_id=42,
    )
    encoded_uri = quote(ontology_uri, safe="")
    http_versions = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/versions/{encoded_uri}",
        headers=headers,
    )
    assert http_versions.status_code == 200
    assert len(mcp_versions.get("versions") or []) >= 1
    assert mcp_versions.get("versions") == http_versions.json()


def test_search_and_graph_ontology_mcp_matches_http(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _auth_client(e2e_dir)
    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    ontology_uri = seeded.json()["ontology_uri"]

    mcp_graph = _mcp_call(
        client,
        workspace_id,
        headers,
        "get_ontology_graph",
        {"uri": ontology_uri},
        rpc_id=50,
    )
    http_graph = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/graph",
        headers=headers,
        params={"uri": ontology_uri},
    )
    assert http_graph.status_code == 200
    assert mcp_graph.get("graph") == http_graph.json()

    mcp_search = _mcp_call(
        client,
        workspace_id,
        headers,
        "search_ontology_entities",
        {"q": "E2EClass", "limit": 20},
        rpc_id=51,
    )
    http_search = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/search",
        headers=headers,
        params={"q": "E2EClass", "limit": 20},
    )
    assert http_search.status_code == 200
    assert mcp_search.get("results") == http_search.json()
