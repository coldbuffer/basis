"""Demo workspace pack + MCP search vs derived reasoning (续费签字)."""

import json

import pytest
from fastapi.testclient import TestClient

from basis.domain.knowledge.demo.pack_v1 import (
    DEMO_GROUND_FACTS,
    DEMO_INFERRED_CONCLUSION,
    DEMO_RULE_BODY,
)
from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.demo_workspace import create_workspace_with_demo

pytest.importorskip("semantica")


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


def test_demo_workspace_mcp_search_vs_derived_reasoning(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "demo@example.com", "password": "password1", "display_name": "Demo"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)

    search = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "search_chunks",
        {"query": "续费 签字 程浩", "limit": 10, "mode": "keyword"},
        rpc_id=1,
    )
    chunk_text = " ".join((c.get("text") or "") for c in search.get("chunks", []))
    assert "renewalOrderSignatory" not in chunk_text
    assert "续费订单签字" not in chunk_text

    entities = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "query_graph",
        {"mode": "entities", "query": "唐悦"},
        rpc_id=2,
    )
    ledger = entities.get("ledger_entities") or []
    assert any(e.get("canonical_label") == "唐悦" for e in ledger)

    derived = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "list_derived_facts",
        {"limit": 50},
        rpc_id=3,
    )
    facts = derived.get("derived_facts") or []
    assert any(
        "renewalOrderSignatory" in (f.get("predicate_uri") or "") for f in facts
    ), facts

    tang = next(e for e in ledger if e.get("canonical_label") == "唐悦")
    entity_derived = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "list_derived_facts",
        {"entity_id": tang["id"], "limit": 50},
        rpc_id=4,
    )
    ed = entity_derived.get("derived_facts") or []
    assert ed, "唐悦 should have derived facts"
    derivations = ed[0].get("derivations") or []
    premise_text = " ".join(d.get("premise_id") or "" for d in derivations)
    assert "activeAgreement" in premise_text
    assert "commercialContact" in premise_text

    mappings = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "list_mappings",
        {"status": "confirmed", "limit": 100},
        rpc_id=5,
    )
    assert mappings.get("mappings"), "demo pack should ship confirmed ontology mappings"

    rules = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "list_rules",
        {"limit": 20},
        rpc_id=6,
    )
    assert any("renewalOrderSignatory" in (r.get("body") or "") for r in rules.get("rules") or [])

    typed = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "list_typed_facts",
        {"limit": 50},
        rpc_id=7,
    )
    stmt_id = next(
        (f.get("from_statement_id") for f in typed.get("facts") or [] if f.get("from_statement_id")),
        None,
    )
    assert stmt_id, "typed facts should link to source statements"
    statement = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "get_statement",
        {"statement_id": stmt_id},
        rpc_id=8,
    ).get("statement") or {}
    assert statement.get("statement_id") == stmt_id

    caps = client.get(
        f"/api/v1/workspaces/{workspace_id}/capabilities",
        headers=headers,
    ).json()
    assert "run_reasoning" in (caps.get("mcp_tools") or [])
    assert caps.get("upload_max_bytes"), "capabilities should include runtime limits"
    assert caps.get("chunk_search_max_limit")

    rerun = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "run_reasoning",
        {
            "facts": list(DEMO_GROUND_FACTS),
            "rules": [DEMO_RULE_BODY],
            "apply_to_graph": False,
        },
        rpc_id=10,
    )
    inferred = rerun.get("inferred_facts") or []
    assert DEMO_INFERRED_CONCLUSION in inferred

    auto = _mcp_tool_json(
        client,
        workspace_id,
        headers,
        "run_reasoning",
        {"rules": [DEMO_RULE_BODY], "apply_to_graph": False},
        rpc_id=11,
    )
    assert auto.get("facts_source") == "typed_facts"
    assert DEMO_INFERRED_CONCLUSION in (auto.get("inferred_facts") or [])

    http_auto = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={"rules": [DEMO_RULE_BODY], "apply_to_graph": False},
    )
    assert http_auto.status_code == 200
    http_body = http_auto.json()
    assert http_body.get("facts_source") == "typed_facts"
    assert DEMO_INFERRED_CONCLUSION in (http_body.get("inferred_facts") or [])
