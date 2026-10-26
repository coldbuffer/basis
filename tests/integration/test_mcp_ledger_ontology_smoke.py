"""One-shot MCP tools/call smoke for ledger mapping + ontology hub tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.application.tool_catalog.mcp_access import mcp_tool_access
from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from tests.contract.test_contract_mcp_ledger_ontology_schemas import (
    LEDGER_MAPPING_TOOLS,
    ONTOLOGY_HUB_TOOLS,
)

ALL_LEDGER_ONTOLOGY_TOOLS = frozenset({**LEDGER_MAPPING_TOOLS, **ONTOLOGY_HUB_TOOLS})
READ_TOOLS_EMPTY_OK = frozenset(
    name
    for name in ALL_LEDGER_ONTOLOGY_TOOLS
    if mcp_tool_access(name) == "read"
    and name
    not in {
        "get_ontology_graph",
        "search_ontology_entities",
        "list_ontology_drafts",
        "get_ontology_draft",
        "get_ontology_proposal",
        "list_ontology_versions",
        "compare_ontology_versions",
    }
)


def _client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "smoke@example.com", "password": "password1", "display_name": "S"},
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


def _assert_ok_payload(name: str, payload: dict) -> None:
    assert payload.get("code") != "forbidden", name
    err = payload.get("error")
    assert err not in {"forbidden", "ontology_hub_unavailable"}, (name, payload)
    if err == "unknown tool":
        pytest.fail(name)


def test_ledger_ontology_tools_registered_in_mcp_list(tmp_path: Path) -> None:
    client, workspace_id, headers = _client(tmp_path)
    tools = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    ).json()
    names = {t["name"] for t in tools["result"]["tools"]}
    missing = sorted(ALL_LEDGER_ONTOLOGY_TOOLS - names)
    assert missing == []


@pytest.mark.parametrize("tool_name", sorted(READ_TOOLS_EMPTY_OK))
def test_read_tools_call_on_empty_workspace(tmp_path: Path, tool_name: str) -> None:
    client, workspace_id, headers = _client(tmp_path)
    args: dict = {}
    if tool_name in {"list_mappings", "list_surface_phrases", "list_entity_type_object_labels"}:
        args["limit"] = 10
    payload = _mcp(client, workspace_id, headers, tool_name, args, rpc_id=2)
    _assert_ok_payload(tool_name, payload)


def test_full_ledger_ontology_tool_smoke(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client, workspace_id, headers = _client(e2e_dir)
    rpc = 10

    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    assert seeded.status_code == 200
    seed = seeded.json()
    ontology_uri = seed["ontology_uri"]
    proposal_id = seed["proposal_id"]
    class_uri = ontology_uri.replace("#ontology", "#E2EClass")

    rpc += 1
    p = _mcp(client, workspace_id, headers, "get_ontology_graph", {"uri": ontology_uri}, rpc_id=rpc)
    _assert_ok_payload("get_ontology_graph", p)
    assert p.get("graph") is not None

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "search_ontology_entities",
        {"q": "E2EClass", "limit": 10},
        rpc_id=rpc,
    )
    _assert_ok_payload("search_ontology_entities", p)

    rpc += 1
    drafts = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_drafts",
        {"ontology_uri": ontology_uri},
        rpc_id=rpc,
    )
    draft_id = drafts["drafts"][0]["draft_id"]

    rpc += 1
    p = _mcp(client, workspace_id, headers, "get_ontology_draft", {"draft_id": draft_id}, rpc_id=rpc)
    _assert_ok_payload("get_ontology_draft", p)

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "get_ontology_proposal",
        {"proposal_id": proposal_id},
        rpc_id=rpc,
    )
    _assert_ok_payload("get_ontology_proposal", p)

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "comment_ontology_proposal",
        {
            "proposal_id": proposal_id,
            "element_uri": class_uri,
            "text": "smoke comment",
        },
        rpc_id=rpc,
    )
    _assert_ok_payload("comment_ontology_proposal", p)

    base = ontology_uri.split("#", 1)[0]
    rpc += 1
    saved = _mcp(
        client,
        workspace_id,
        headers,
        "save_ontology_draft",
        {
            "ontology_uri": ontology_uri,
            "summary": "smoke draft",
            "diff": {"added_classes": [f"{base}#SmokeClass"]},
        },
        rpc_id=rpc,
    )
    _assert_ok_payload("save_ontology_draft", saved)

    rpc += 1
    submitted = _mcp(
        client,
        workspace_id,
        headers,
        "submit_ontology_proposal",
        {
            "draft_id": saved["draft"]["draft_id"],
            "ontology_uri": ontology_uri,
            "summary": "smoke proposal",
        },
        rpc_id=rpc,
    )
    proposal2 = submitted["proposal"]["proposal_id"]

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "approve_ontology_proposal",
        {"proposal_id": proposal2},
        rpc_id=rpc,
    )
    _assert_ok_payload("approve_ontology_proposal", p)

    rpc += 1
    pub = _mcp(
        client,
        workspace_id,
        headers,
        "publish_ontology_proposal",
        {"proposal_id": proposal2},
        rpc_id=rpc,
    )
    _assert_ok_payload("publish_ontology_proposal", pub)
    assert pub.get("registry", {}).get("registered") in {True, False}

    rpc += 1
    registry_after = _mcp(client, workspace_id, headers, "list_ontology_registry", {}, rpc_id=rpc)
    _assert_ok_payload("list_ontology_registry", registry_after)
    assert any(row.get("uri") == ontology_uri for row in registry_after.get("registry") or [])

    rpc += 1
    versions = _mcp(
        client,
        workspace_id,
        headers,
        "list_ontology_versions",
        {"ontology_uri": ontology_uri},
        rpc_id=rpc,
    )
    version_id = versions["versions"][0]["version_id"]

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "compare_ontology_versions",
        {
            "ontology_uri": ontology_uri,
            "version1": version_id,
            "version2": version_id,
        },
        rpc_id=rpc,
    )
    _assert_ok_payload("compare_ontology_versions", p)

    rpc += 1
    mapping = _mcp(
        client,
        workspace_id,
        headers,
        "propose_mapping",
        {
            "signature": "surface:smoke_tool",
            "status": "proposed",
            "target_kind": "property",
            "direction": "forward",
        },
        rpc_id=rpc,
    )
    _assert_ok_payload("propose_mapping", mapping)

    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "update_mapping_status",
        {"mapping_id": mapping["mapping"]["id"], "status": "confirmed"},
        rpc_id=rpc,
    )
    _assert_ok_payload("update_mapping_status", p)

    seeded2 = client.post(
        f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal",
        headers=headers,
    ).json()
    rpc += 1
    p = _mcp(
        client,
        workspace_id,
        headers,
        "reject_ontology_proposal",
        {"proposal_id": seeded2["proposal_id"]},
        rpc_id=rpc,
    )
    _assert_ok_payload("reject_ontology_proposal", p)
