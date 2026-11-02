"""Workspace-scoped Explorer adapter routes (temporal, enrich, provenance)."""

import json

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def test_temporal_bounds_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "e@example.com", "password": "password1", "display_name": "E"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "t1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    bounds = client.get(f"/api/v1/workspaces/{workspace_id}/temporal/bounds", headers=headers)
    assert bounds.status_code == 200
    body = bounds.json()
    assert "min" in body and "max" in body


def test_temporal_diff_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "td@example.com", "password": "password1", "display_name": "TD"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "td1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    bounds = client.get(f"/api/v1/workspaces/{workspace_id}/temporal/bounds", headers=headers)
    assert bounds.status_code == 200
    b = bounds.json()
    t_from, t_to = b["min"], b["max"]

    diff = client.get(
        f"/api/v1/workspaces/{workspace_id}/temporal/diff",
        headers=headers,
        params={"from": t_from, "to": t_to},
    )
    assert diff.status_code == 200
    payload = diff.json()
    assert isinstance(payload, dict)


def test_graph_diff_includes_edges_summary(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gd@example.com", "password": "password1", "display_name": "GD"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "gd1", "text": "Carol knows Dave.", "wait": True, "extract": True},
    )

    bounds = client.get(f"/api/v1/workspaces/{workspace_id}/temporal/bounds", headers=headers).json()
    t_from = bounds.get("min") or "2020-01-01T00:00:00"
    t_to = bounds.get("max") or "2030-01-01T00:00:00"
    diff = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/diff",
        headers=headers,
        params={"from": t_from, "to": t_to},
    )
    assert diff.status_code == 200
    body = diff.json()
    assert "summary" in body
    assert "added_edges" in body
    assert "modified_nodes" in body


def test_ingest_temporal_bounds_align_with_graph_diff(tmp_path) -> None:
    """F-TIM-03: ledger bounds, end snapshot, and diff from min→max stay consistent after ingest."""
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "tim@example.com", "password": "password1", "display_name": "Tim"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "tim1",
            "text": "Grace knows Henry.",
            "wait": True,
            "extract": True,
        },
    )

    bounds = client.get(f"/api/v1/workspaces/{workspace_id}/temporal/bounds", headers=headers).json()
    t_from = bounds.get("min") or "2020-01-01T00:00:00"
    t_to = bounds.get("max") or "2030-01-01T00:00:00"

    diff = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/diff",
        headers=headers,
        params={"from": t_from, "to": t_to},
    )
    assert diff.status_code == 200
    body = diff.json()
    added_nodes = list(body.get("added_nodes") or [])
    if not added_nodes:
        pytest.skip("ingest produced no added nodes in diff range (extract noop)")

    snap_at = body.get("to_time") or t_to
    snap = client.get(
        f"/api/v1/workspaces/{workspace_id}/temporal/snapshot",
        headers=headers,
        params={"at": snap_at},
    )
    assert snap.status_code == 200
    snap_body = snap.json()
    assert isinstance(snap_body.get("active_node_ids"), list)
    assert isinstance(snap_body.get("active_node_count"), int)
    snap_ids = {n.get("id") for n in (snap_body.get("nodes") or []) if n.get("id")}
    for node_id in added_nodes:
        assert node_id in snap_ids

    if bounds.get("min") and bounds.get("max"):
        ledger_diff = client.get(
            f"/api/v1/workspaces/{workspace_id}/graph/diff",
            headers=headers,
            params={"from": bounds["min"], "to": bounds["max"]},
        )
        assert ledger_diff.status_code == 200


def test_enrich_dedup_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "d@example.com", "password": "password1", "display_name": "D"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "d1", "text": "Alice knows Bob. Alice works with Bob.", "wait": True, "extract": True},
    )

    dedup = client.post(
        f"/api/v1/workspaces/{workspace_id}/enrich/dedup",
        headers=headers,
        json={"threshold": 0.5},
    )
    assert dedup.status_code == 200
    payload = dedup.json()
    assert "duplicates" in payload
    assert "total_flagged" in payload


def test_sparql_select_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "s@example.com", "password": "password1", "display_name": "S"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "s1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    sparql = client.post(
        f"/api/v1/workspaces/{workspace_id}/sparql",
        headers=headers,
        json={"query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5"},
    )
    assert sparql.status_code == 200
    body = sparql.json()
    assert "columns" in body and "rows" in body
    assert body.get("error") in (None, "")


def test_provenance_lineage_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "p@example.com", "password": "password1", "display_name": "P"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "p1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    nodes = client.get(f"/api/v1/workspaces/{workspace_id}/graph/nodes?limit=5", headers=headers)
    assert nodes.status_code == 200
    node_list = nodes.json().get("nodes") or []
    if not node_list:
        pytest.skip("no projected nodes to trace")

    node_id = node_list[0]["id"]
    lineage = client.get(
        f"/api/v1/workspaces/{workspace_id}/provenance",
        headers=headers,
        params={"node_id": node_id},
    )
    assert lineage.status_code == 200
    body = lineage.json()
    assert "nodes" in body and "edges" in body


def test_decisions_list_empty_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "c@example.com", "password": "password1", "display_name": "C"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "c1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    decisions = client.get(f"/api/v1/workspaces/{workspace_id}/decisions", headers=headers)
    assert decisions.status_code == 200
    assert isinstance(decisions.json(), list)


def test_distance_matrix_after_ingest(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "dm@example.com", "password": "password1", "display_name": "DM"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "dm1", "text": "Alice knows Bob. Bob knows Carol.", "wait": True, "extract": True},
    )

    nodes = client.get(f"/api/v1/workspaces/{workspace_id}/graph/nodes", headers=headers, params={"limit": 20})
    assert nodes.status_code == 200
    node_list = nodes.json().get("nodes") or []
    if len(node_list) < 2:
        pytest.skip("ingest produced fewer than two graph nodes")

    ids = [n["id"] for n in node_list[:3]]
    matrix = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/distance-matrix",
        headers=headers,
        json={"node_ids": ids, "metric": "hops"},
    )
    assert matrix.status_code == 200
    body = matrix.json()
    assert "distances" in body or "matrix" in body


def test_reasoning_run_without_graph_write(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "r@example.com", "password": "password1", "display_name": "R"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    reasoning = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={
            "facts": ["inhibits(Metformin, mTOR)", "causes(mTOR, Neurodegeneration)"],
            "rules": [
                "IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) THEN candidate(Metformin, Alzheimer's)"
            ],
            "mode": "forward",
            "apply_to_graph": False,
        },
    )
    assert reasoning.status_code == 200
    body = reasoning.json()
    assert "inferred_facts" in body
    assert body.get("proof_chains")
    assert body["proof_chains"][0].get("premises")


def test_graph_import_export_roundtrip(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "io@example.com", "password": "password1", "display_name": "IO"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    payload = {
        "nodes": [
            {"id": "import-node-1", "type": "entity", "properties": {"content": "Hello import"}},
        ],
        "edges": [],
    }
    files = {
        "file": ("graph.json", json.dumps(payload), "application/json"),
    }
    blocked = client.post(f"/api/v1/workspaces/{workspace_id}/import", headers=headers, files=files)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "import_requires_review"

    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/graph-import",
        headers=headers,
        files=files,
    )
    assert proposed.status_code == 200
    item_id = proposed.json()["item"]["id"]
    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item_id}/approve",
        headers=headers,
        json={},
    )
    assert approved.status_code == 200
    assert approved.json().get("import", {}).get("nodes_imported", 0) >= 1

    exported = client.post(
        f"/api/v1/workspaces/{workspace_id}/export",
        headers=headers,
        json={"format": "json"},
    )
    assert exported.status_code == 200
    assert exported.headers.get("content-type", "").startswith("application/json")

    subgraph = client.post(
        f"/api/v1/workspaces/{workspace_id}/export",
        headers=headers,
        json={"format": "json", "node_ids": ["import-node-1", "does-not-exist"]},
    )
    assert subgraph.status_code == 200
    assert subgraph.headers.get("content-type", "").startswith("application/json")

    ttl = client.post(
        f"/api/v1/workspaces/{workspace_id}/export",
        headers=headers,
        json={"format": "ttl"},
    )
    if ttl.status_code == 503:
        pytest.skip("RDF export dependencies unavailable")
    assert ttl.status_code == 200
    ctype = (ttl.headers.get("content-type") or "").lower()
    assert "turtle" in ctype or ttl.content[:1]

    audit = client.get(f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations", headers=headers)
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()["events"]]
    assert "workspace.graph.import" in actions or "workspace.graph.import_proposed" in actions
    assert "workspace.graph.export" in actions


def test_semantic_neighborhood_unknown_node_returns_coded_detail(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "sem@example.com", "password": "password1", "display_name": "Sem"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "s1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    missing = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/semantic-neighborhood",
        headers=headers,
        params={"node_id": "definitely-missing-node-id"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "semantic_node_not_found"


def test_graph_path_requires_source_and_target(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "path@example.com", "password": "password1", "display_name": "Path"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "p1", "text": "Alice knows Bob.", "wait": True, "extract": True},
    )

    bad = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/path",
        headers=headers,
        params={"source": "", "target": "x", "algorithm": "bfs"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "bad_path"
