"""MCP ontology draft/proposal governance flows."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def _e2e_client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_dir)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gov-mcp@example.com", "password": "password1", "display_name": "G"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _seed_proposal(client: TestClient, workspace_id: str, headers: dict) -> dict:
    resp = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    assert resp.status_code == 200
    return resp.json()


def _mcp(
    client: TestClient,
    workspace_id: str,
    headers: dict,
    name: str,
    args: dict,
    *,
    rpc_id: int,
    expect_error: bool = False,
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
    result = resp.json()["result"]
    if expect_error:
        assert result["isError"] is True
    else:
        assert result["isError"] is False, result.get("content")
    return json.loads(result["content"][0]["text"])


@pytest.fixture
def e2e_ctx(tmp_path: Path):
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")
    return _e2e_client(tmp_path)


def test_list_ontology_proposals_mcp_matches_http(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    proposal_id = seeded["proposal_id"]
    ontology_uri = seeded["ontology_uri"]

    mcp = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_proposals",
        {"ontology_uri": ontology_uri, "state": "proposed"},
        rpc_id=1,
    )
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals",
        headers=headers,
        params={"ontology_uri": ontology_uri, "state": "proposed"},
    )
    assert http.status_code == 200
    assert any(p["proposal_id"] == proposal_id for p in mcp.get("proposals") or [])
    assert mcp.get("proposals") == http.json()


def test_reject_ontology_proposal_mcp(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    proposal_id = _seed_proposal(client, workspace_id, headers)["proposal_id"]

    rejected = _mcp(
        client,
        workspace_id,
        headers,
        "reject_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=2,
    )
    assert rejected.get("status") == "rejected"
    assert (
        client.get(
            f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}",
            headers=headers,
        ).json()["state"]
        == "rejected"
    )


def test_comment_ontology_proposal_mcp(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    proposal_id = seeded["proposal_id"]
    class_uri = seeded["ontology_uri"].replace("#ontology", "#E2EClass")

    commented = _mcp(
        client,
        workspace_id,
        headers,
        "comment_ontology_proposal",
        {
            "proposal_id": proposal_id,
            "element_uri": class_uri,
            "text": "Review note from MCP",
        },
        rpc_id=3,
    )
    assert commented.get("status") == "commented"
    proposal = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{proposal_id}",
        headers=headers,
    ).json()
    assert any(c.get("text") == "Review note from MCP" for c in proposal.get("comments") or [])


def test_get_ontology_draft_mcp_matches_http(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    ontology_uri = seeded["ontology_uri"]
    drafts = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_drafts",
        {"ontology_uri": ontology_uri},
        rpc_id=4,
    )
    draft_id = drafts["drafts"][0]["draft_id"]

    mcp = _mcp(
        client,
        workspace_id,
        headers,
        "get_ontology_draft",
        {"draft_id": draft_id},
        rpc_id=5,
    )
    http = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/draft/{draft_id}",
        headers=headers,
    )
    assert http.status_code == 200
    assert mcp.get("draft") == http.json()


def test_save_draft_and_submit_proposal_mcp(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    ontology_uri = seeded["ontology_uri"]
    base = ontology_uri.split("#", 1)[0]
    extra_class = f"{base}#McpAddedClass"

    saved = _mcp(
        client,
        workspace_id,
        headers,
        "save_ontology_draft",
        {
            "ontology_uri": ontology_uri,
            "summary": "MCP second draft",
            "diff": {"added_classes": [extra_class]},
        },
        rpc_id=6,
    )
    draft_id = saved["draft"]["draft_id"]

    submitted = _mcp(
        client,
        workspace_id,
        headers,
        "submit_ontology_proposal",
        {
            "draft_id": draft_id,
            "ontology_uri": ontology_uri,
            "summary": "MCP submitted proposal",
        },
        rpc_id=7,
    )
    new_id = submitted["proposal"]["proposal_id"]
    assert submitted["proposal"]["state"] == "proposed"
    assert (
        client.get(
            f"/api/v1/workspaces/{workspace_id}/ontology/proposals/{new_id}",
            headers=headers,
        ).status_code
        == 200
    )


def test_compare_ontology_versions_missing_version_mcp_error(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    proposal_id = seeded["proposal_id"]
    ontology_uri = seeded["ontology_uri"]

    _mcp(
        client,
        workspace_id,
        headers,
        "approve_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=8,
    )
    _mcp(
        client,
        workspace_id,
        headers,
        "publish_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=9,
    )
    versions = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_versions",
        {"ontology_uri": ontology_uri},
        rpc_id=10,
    )["versions"]
    version_id = versions[0]["version_id"]

    payload = _mcp(
        client,
        workspace_id,
        headers,
        "compare_ontology_versions",
        {
            "ontology_uri": ontology_uri,
            "version1": version_id,
            "version2": "version_does_not_exist",
        },
        rpc_id=11,
    )
    assert payload.get("error") == "not_found"
    assert payload.get("message")


def test_compare_ontology_versions_mcp_matches_http(e2e_ctx) -> None:
    client, workspace_id, headers = e2e_ctx
    seeded = _seed_proposal(client, workspace_id, headers)
    proposal_id = seeded["proposal_id"]
    ontology_uri = seeded["ontology_uri"]

    _mcp(client, workspace_id, headers, "approve_ontology_proposal", {"proposal_id": proposal_id}, rpc_id=12)
    _mcp(client, workspace_id, headers, "publish_ontology_proposal", {"proposal_id": proposal_id}, rpc_id=13)
    versions = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_versions",
        {"ontology_uri": ontology_uri},
        rpc_id=14,
    )["versions"]
    assert len(versions) >= 1
    version_id = versions[0]["version_id"]

    mcp = _mcp(
        client,
        workspace_id,
        headers,
        "compare_ontology_versions",
        {
            "ontology_uri": ontology_uri,
            "version1": version_id,
            "version2": version_id,
        },
        rpc_id=15,
    )
    encoded = quote(ontology_uri, safe="")
    http = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/versions/{encoded}/compare",
        headers=headers,
        json={"version1": version_id, "version2": version_id},
    )
    assert http.status_code == 200
    assert mcp.keys() == http.json().keys()
