"""HTTP core list routes and MCP tools/call return the same ledger payloads."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.demo_workspace import create_workspace_with_demo

pytest.importorskip("semantica")


def _session_client(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "parity-doc@example.com", "password": "password1", "display_name": "D"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "parity-doc",
            "text": "Vienna is the capital of Austria.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )
    return client, workspace_id, headers


def _mcp_payload(
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


def test_demo_http_mcp_parity_ledger_and_config_reads(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "parity@example.com", "password": "password1", "display_name": "P"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)

    http_typed = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/typed-facts",
        headers=headers,
        params={"limit": 200},
    ).json()
    mcp_typed = _mcp_payload(
        client, workspace_id, headers, "list_typed_facts", {"limit": 200}, rpc_id=1
    )
    assert http_typed["facts"] == mcp_typed["facts"]

    http_derived = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/derived-facts",
        headers=headers,
        params={"limit": 200},
    ).json()
    mcp_derived = _mcp_payload(
        client, workspace_id, headers, "list_derived_facts", {"limit": 200}, rpc_id=2
    )
    assert http_derived["derived_facts"] == mcp_derived["derived_facts"]

    http_rules = client.get(
        f"/api/v1/workspaces/{workspace_id}/rules",
        headers=headers,
        params={"limit": 100},
    ).json()
    mcp_rules = _mcp_payload(
        client, workspace_id, headers, "list_rules", {"limit": 100}, rpc_id=3
    )
    assert http_rules["rules"] == mcp_rules["rules"]

    http_mappings = client.get(
        f"/api/v1/workspaces/{workspace_id}/mappings",
        headers=headers,
        params={"status": "confirmed", "limit": 100},
    ).json()
    mcp_mappings = _mcp_payload(
        client,
        workspace_id,
        headers,
        "list_mappings",
        {"status": "confirmed", "limit": 100},
        rpc_id=4,
    )
    assert http_mappings["mappings"] == mcp_mappings["mappings"]

    stmt_id = next(
        f["from_statement_id"] for f in http_typed["facts"] if f.get("from_statement_id")
    )
    http_stmt = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/statements/{stmt_id}",
        headers=headers,
    ).json()
    mcp_stmt = _mcp_payload(
        client, workspace_id, headers, "get_statement", {"statement_id": stmt_id}, rpc_id=5
    )
    assert http_stmt == mcp_stmt

    http_review = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"status": "open", "limit": 50},
    ).json()
    mcp_review = _mcp_payload(
        client,
        workspace_id,
        headers,
        "list_review_items",
        {"status": "open", "limit": 50},
        rpc_id=7,
    )
    assert http_review["items"] == mcp_review["items"]

    demo_rule = http_rules["rules"][0]["body"]
    http_run = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={"rules": [demo_rule], "apply_to_graph": False},
    ).json()
    mcp_run = _mcp_payload(
        client,
        workspace_id,
        headers,
        "run_reasoning",
        {"rules": [demo_rule], "apply_to_graph": False},
        rpc_id=9,
    )
    assert http_run.get("facts_source") == mcp_run.get("facts_source") == "typed_facts"
    assert http_run.get("inferred_facts") == mcp_run.get("inferred_facts")


def test_search_and_find_entities_http_mcp_parity(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)

    http_search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "Vienna", "limit": 5},
    ).json()
    mcp_search = _mcp_payload(
        client,
        workspace_id,
        headers,
        "search_chunks",
        {"query": "Vienna", "limit": 5},
        rpc_id=1,
    )
    assert http_search.get("chunks") == mcp_search.get("chunks")

    http_find = client.get(
        f"/api/v1/workspaces/{workspace_id}/entities/find",
        headers=headers,
        params={"q": "Vienna", "limit": 5},
    ).json()
    mcp_find = _mcp_payload(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "entities", "query": "Vienna", "limit": 5},
        rpc_id=2,
    )
    assert http_find == mcp_find

    http_graph = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/search",
        headers=headers,
        json={"query": "Vienna", "limit": 5},
    ).json()
    mcp_graph = _mcp_payload(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "search", "query": "Vienna", "limit": 5},
        rpc_id=3,
    )
    assert http_graph.get("results") == mcp_graph.get("results")


def test_demo_neighbors_http_mcp_parity(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "nb@example.com", "password": "password1", "display_name": "N"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)

    found = client.get(
        f"/api/v1/workspaces/{workspace_id}/entities/find",
        headers=headers,
        params={"q": "唐悦", "limit": 5},
    ).json()
    tang = next(
        e for e in found.get("ledger_entities") or [] if e.get("canonical_label") == "唐悦"
    )
    node_id = tang["id"]
    depth = 2

    http_nb = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/nodes/{node_id}/neighbors",
        headers=headers,
        params={"depth": depth},
    ).json()
    mcp_nb = _mcp_payload(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "neighbors", "node_id": node_id, "depth": depth},
        rpc_id=1,
    )
    assert http_nb["node_id"] == mcp_nb["node_id"]
    assert http_nb["depth"] == mcp_nb["depth"]
    assert http_nb["neighbors"] == mcp_nb["neighbors"]


def test_describe_workspace_counts_match_get_workspace(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    workspace = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers).json()
    described = _mcp_payload(
        client, workspace_id, headers, "get_graph_summary", {}, rpc_id=1
    )
    assert described["workspace_id"] == workspace_id
    assert described["name"] == workspace["name"]
    for key in ("document_count", "chunk_count", "entity_count", "statement_count"):
        assert described.get(key) == workspace.get(key)


def test_get_chunk_core_payload_parity(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "Vienna", "limit": 1},
    ).json()
    first = search["chunks"][0]
    chunk_id = first.get("chunk_id") or first.get("id")
    assert chunk_id
    http_chunk = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/chunks/{chunk_id}",
        headers=headers,
    ).json()
    mcp_chunk = _mcp_payload(
        client, workspace_id, headers, "get_chunk", {"chunk_id": chunk_id}, rpc_id=1
    )
    assert http_chunk["chunk"] == mcp_chunk["chunk"]


def test_demo_entity_facts_http_mcp_parity(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ef@example.com", "password": "password1", "display_name": "E"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)
    tang = next(
        e
        for e in client.get(
            f"/api/v1/workspaces/{workspace_id}/entities/find",
            headers=headers,
            params={"q": "唐悦"},
        ).json()["ledger_entities"]
        if e.get("canonical_label") == "唐悦"
    )
    http_facts = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{tang['id']}/facts",
        headers=headers,
        params={"limit": 50},
    ).json()
    mcp_facts = _mcp_payload(
        client,
        workspace_id,
        headers,
        "entity_facts",
        {"entity_id": tang["id"], "limit": 50},
        rpc_id=1,
    )
    assert http_facts["facts"] == mcp_facts["facts"]
    assert http_facts["derived_facts"] == mcp_facts["derived_facts"]


def test_get_rule_http_mcp_parity(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rule@example.com", "password": "password1", "display_name": "R"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)
    rule_id = client.get(
        f"/api/v1/workspaces/{workspace_id}/rules",
        headers=headers,
        params={"limit": 10},
    ).json()["rules"][0]["id"]
    http_rule = client.get(
        f"/api/v1/workspaces/{workspace_id}/rules/{rule_id}",
        headers=headers,
    ).json()
    mcp_rule = _mcp_payload(
        client, workspace_id, headers, "get_rule", {"rule_id": rule_id}, rpc_id=1
    )
    assert http_rule == mcp_rule


_REMEMBER_PARITY_MARKER = "HTTP_MCP_REMEMBER_PARITY_2026"


def test_remember_propose_get_approve_http_mcp_parity(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    content = f"Acme note {_REMEMBER_PARITY_MARKER} via parity test."

    http_proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": content},
    ).json()
    mcp_proposed = _mcp_payload(
        client,
        workspace_id,
        headers,
        "propose_remember",
        {"content": content + " (mcp second)"},
        rpc_id=1,
    )
    for payload in (http_proposed, mcp_proposed):
        assert payload.get("review_item_id")
        assert payload.get("statement_id")

    http_item_id = http_proposed["review_item_id"]
    http_item = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items/{http_item_id}",
        headers=headers,
    ).json()
    mcp_item = _mcp_payload(
        client,
        workspace_id,
        headers,
        "get_review_item",
        {"item_id": http_item_id},
        rpc_id=2,
    )
    assert http_item == mcp_item

    http_approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{http_item_id}/approve",
        headers=headers,
        json={"rationale": "parity http"},
    ).json()
    mcp_item_id = mcp_proposed["review_item_id"]
    mcp_approved = _mcp_payload(
        client,
        workspace_id,
        headers,
        "approve_review_item",
        {"item_id": mcp_item_id, "rationale": "parity mcp"},
        rpc_id=3,
    )
    assert http_approved["item"]["status"] == "approved"
    assert mcp_approved["item"]["status"] == "approved"


def test_reject_review_item_http_mcp_parity(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)

    http_item_id = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": "Reject parity HTTP proposal."},
    ).json()["review_item_id"]
    mcp_item_id = _mcp_payload(
        client,
        workspace_id,
        headers,
        "propose_remember",
        {"content": "Reject parity MCP proposal."},
        rpc_id=1,
    )["review_item_id"]

    http_rejected = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{http_item_id}/reject",
        headers=headers,
        json={"rationale": "parity http reject"},
    ).json()
    mcp_rejected = _mcp_payload(
        client,
        workspace_id,
        headers,
        "reject_review_item",
        {"item_id": mcp_item_id, "rationale": "parity mcp reject"},
        rpc_id=2,
    )
    assert http_rejected["item"]["status"] == "rejected"
    assert mcp_rejected["item"]["status"] == "rejected"

    http_get = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items/{http_item_id}",
        headers=headers,
    ).json()
    mcp_get = _mcp_payload(
        client,
        workspace_id,
        headers,
        "get_review_item",
        {"item_id": mcp_item_id},
        rpc_id=3,
    )
    assert http_get["item"]["status"] == "rejected"
    assert mcp_get["item"]["status"] == "rejected"


def _first_chunk_id(client: TestClient, workspace_id: str, headers: dict[str, str]) -> str:
    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "Vienna", "limit": 1},
    ).json()
    first = search["chunks"][0]
    chunk_id = first.get("chunk_id") or first.get("id")
    assert chunk_id
    return str(chunk_id)


def test_mcp_optional_evidence_chunk_citations(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    chunk_id = _first_chunk_id(client, workspace_id, headers)

    extracted = _mcp_payload(
        client,
        workspace_id,
        headers,
        "extract_entities",
        {"chunk_id": chunk_id},
        rpc_id=1,
    )
    assert extracted.get("evidence", {}).get("chunk_id") == chunk_id
    assert isinstance(extracted.get("entities"), list)

    proposed = _mcp_payload(
        client,
        workspace_id,
        headers,
        "propose_remember",
        {"content": "Vienna is cited from ledger chunk.", "chunk_id": chunk_id},
        rpc_id=2,
    )
    assert proposed.get("chunk_id") == chunk_id

    node_id = "parity-evidence-node"
    added = _mcp_payload(
        client,
        workspace_id,
        headers,
        "add_entity",
        {"id": node_id, "label": "Evidence node", "chunk_id": chunk_id},
        rpc_id=3,
    )
    assert added.get("evidence", {}).get("chunk_id") == chunk_id
    assert added.get("evidence", {}).get("quote")

    reasoning = _mcp_payload(
        client,
        workspace_id,
        headers,
        "run_reasoning",
        {
            "facts": ["parent(Vienna, Austria)"],
            "rules": ["IF parent(Vienna, Austria) THEN ancestor(Vienna, Austria)"],
            "apply_to_graph": False,
            "chunk_id": chunk_id,
        },
        rpc_id=4,
    )
    assert reasoning.get("evidence", {}).get("chunk_id") == chunk_id
    assert reasoning.get("inferred_facts")


def test_chunk_evidence_tools_http_mcp_parity(tmp_path) -> None:
    client, workspace_id, headers = _session_client(tmp_path)
    chunk_id = _first_chunk_id(client, workspace_id, headers)
    content = "HTTP/MCP parity cite from chunk."

    http_proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": content, "chunk_id": chunk_id},
    ).json()
    mcp_proposed = _mcp_payload(
        client,
        workspace_id,
        headers,
        "propose_remember",
        {"content": content + " (mcp)", "chunk_id": chunk_id},
        rpc_id=1,
    )
    assert http_proposed.get("chunk_id") == mcp_proposed.get("chunk_id") == chunk_id

    run_body = {
        "facts": ["parent(Vienna, Austria)"],
        "rules": ["IF parent(Vienna, Austria) THEN ancestor(Vienna, Austria)"],
        "apply_to_graph": False,
        "chunk_id": chunk_id,
    }
    http_run = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json=run_body,
    ).json()
    mcp_run = _mcp_payload(
        client,
        workspace_id,
        headers,
        "run_reasoning",
        run_body,
        rpc_id=2,
    )
    assert http_run.get("evidence") == mcp_run.get("evidence")
    assert http_run.get("inferred_facts") == mcp_run.get("inferred_facts")
