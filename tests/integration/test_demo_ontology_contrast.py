"""
A/B: keyword chunk search vs ontology (typed predicates + derived facts) on demo pack.

续费签字场景：程浩（实施）与唐悦（商务）在关键词里都会「像对接人」，只有本体+推理能得出签字联系人。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from basis.domain.knowledge.demo.pack_v1 import DEMO_INFERRED_CONCLUSION
from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.demo_workspace import create_workspace_with_demo

pytest.importorskip("semantica")

DEMO_KEYWORD_QUERY = "云盾"


def _mcp(
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


def _neighbor_relations(payload: dict) -> list[str]:
    out: list[str] = []
    for item in payload.get("neighbors") or []:
        rel = item.get("relationship") or item.get("edge_type") or item.get("relation")
        if rel:
            out.append(str(rel))
    return out


def test_demo_keyword_vs_ontology_contrast(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "ont@example.com", "password": "password1", "display_name": "Ont"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)

    keyword = _mcp(
        client,
        workspace_id,
        headers,
        "search_chunks",
        {"query": DEMO_KEYWORD_QUERY, "limit": 10, "mode": "keyword"},
        rpc_id=1,
    )
    chunk_blobs = " ".join((c.get("text") or "") for c in keyword.get("chunks") or [])
    assert keyword.get("chunks"), "keyword search should return evidence chunks"
    assert "程浩" in chunk_blobs and "唐悦" in chunk_blobs, chunk_blobs
    assert "renewalOrderSignatory" not in chunk_blobs
    assert "签字" not in chunk_blobs or "未指定续费订单签字人" in chunk_blobs

    tang = next(
        e
        for e in _mcp(
            client,
            workspace_id,
            headers,
            "query_graph",
            {"mode": "entities", "query": "唐悦"},
            rpc_id=2,
        ).get("ledger_entities")
        or []
        if e.get("canonical_label") == "唐悦"
    )
    tang_rels = _neighbor_relations(
        _mcp(
            client,
            workspace_id,
            headers,
            "query_graph",
            {"mode": "neighbors", "node_id": tang["id"], "depth": 2},
            rpc_id=5,
        )
    )
    assert "commercialContact" in tang_rels or "续费报价联系" in tang_rels
    assert "renewalOrderSignatory" in tang_rels
    cheng = next(
        e
        for e in _mcp(
            client,
            workspace_id,
            headers,
            "query_graph",
            {"mode": "entities", "query": "程浩"},
            rpc_id=3,
        ).get("ledger_entities")
        or []
        if e.get("canonical_label") == "程浩"
    )
    cheng_rels = _neighbor_relations(
        _mcp(
            client,
            workspace_id,
            headers,
            "query_graph",
            {"mode": "neighbors", "node_id": cheng["id"], "depth": 2},
            rpc_id=4,
        )
    )
    assert "renewalOrderSignatory" not in cheng_rels
    assert "implementationContact" in cheng_rels or "项目实施对接" in cheng_rels

    typed = _mcp(
        client,
        workspace_id,
        headers,
        "list_typed_facts",
        {"limit": 200},
        rpc_id=6,
    ).get("facts") or []
    typed_predicates = {f.get("predicate_uri") or "" for f in typed}
    assert any("commercialContact" in p for p in typed_predicates)
    assert any("implementationContact" in p for p in typed_predicates)
    assert any("activeAgreement" in p for p in typed_predicates)

    rules = _mcp(
        client,
        workspace_id,
        headers,
        "list_rules",
        {"limit": 50},
        rpc_id=7,
    ).get("rules") or []
    assert any("续费" in (r.get("name") or "") or "renewalOrderSignatory" in (r.get("body") or "") for r in rules)

    derived = _mcp(
        client,
        workspace_id,
        headers,
        "list_derived_facts",
        {"entity_id": tang["id"], "limit": 50},
        rpc_id=8,
    ).get("derived_facts") or []
    assert any("renewalOrderSignatory" in (f.get("predicate_uri") or "") for f in derived)
    assert "renewalOrderSignatory" not in chunk_blobs
    assert DEMO_INFERRED_CONCLUSION.split("(")[0] in "renewalOrderSignatory"
