"""Vocabulary alignment review gate and SQL backfill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.ontology.hub.alignment_review import VOCABULARY_ALIGNMENT_REVIEW_KIND
from basis.domain.ontology.hub.alignment_sql import fetch_alignments_dict
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app
from tests.integration.ontology_hub_sidecar import write_alignment_sidecar

pytest.importorskip("semantica")


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


def test_alignment_upsert_proposed_when_review_required(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign@example.com", "password": "password1", "display_name": "V"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    put_cfg = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 1440,
            "governor_confidence_min": 0.75,
            "vocabulary_alignment_requires_review": True,
        },
    )
    assert put_cfg.status_code == 200
    assert put_cfg.json()["config"]["vocabulary_alignment_requires_review"] is True

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments",
        headers=headers,
        json={
            "source_uri": "http://example.org/a#X",
            "target_uri": "http://example.org/b#Y",
            "relation": "skos:exactMatch",
            "confidence": 0.9,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "proposed"
    assert body["review_item_id"]

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == []

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": VOCABULARY_ALIGNMENT_REVIEW_KIND, "status": "open"},
    ).json()["items"]
    assert len(items) == 1

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{items[0]['id']}/approve",
        headers=headers,
        json={"rationale": "ok"},
    )
    assert approved.status_code == 200

    listed_after = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers
    ).json()
    assert len(listed_after) == 1
    assert listed_after[0]["source_uri"] == "http://example.org/a#X"


def test_alignment_upsert_persisted_in_sql(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-sql@example.com", "password": "password1", "display_name": "VS"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments",
        headers=headers,
        json={
            "source_uri": "http://example.org/s#A",
            "target_uri": "http://example.org/t#B",
            "relation": "skos:exactMatch",
            "confidence": 0.8,
        },
    )
    assert created.status_code == 200
    alignment_id = created.json()["id"]
    assert alignment_id

    knowledge = app.state.knowledge_store
    with knowledge._lock:
        stored = fetch_alignments_dict(knowledge._conn, workspace_id)
    assert alignment_id in stored
    assert stored[alignment_id]["source_uri"] == "http://example.org/s#A"


def test_alignment_proposal_reject_does_not_publish(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-rej@example.com", "password": "password1", "display_name": "VR"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 1440,
            "governor_confidence_min": 0.75,
            "vocabulary_alignment_requires_review": True,
        },
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments",
        headers=headers,
        json={
            "source_uri": "http://example.org/r#a",
            "target_uri": "http://example.org/r#b",
            "relation": "skos:exactMatch",
            "confidence": 0.9,
        },
    ).json()
    review_item_id = created["review_item_id"]

    rejected = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{review_item_id}/reject",
        headers=headers,
        json={"rationale": "no"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["item"]["status"] == "rejected"

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers).json()
    assert listed == []


def test_alignment_delete_proposed_when_review_required(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-del@example.com", "password": "password1", "display_name": "VD"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    published = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments",
        headers=headers,
        json={
            "source_uri": "http://example.org/d#1",
            "target_uri": "http://example.org/d#2",
            "relation": "skos:exactMatch",
            "confidence": 0.9,
        },
    ).json()
    alignment_id = published["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 1440,
            "governor_confidence_min": 0.75,
            "vocabulary_alignment_requires_review": True,
        },
    )

    proposed = client.delete(
        f"/api/v1/workspaces/{workspace_id}/ontology/alignments",
        headers=headers,
        params={"id": alignment_id},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "proposed"
    assert body["review_item_id"]

    still = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers).json()
    assert len(still) == 1
    assert still[0]["id"] == alignment_id


def test_alignment_proposal_approve_via_mcp(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-mcp@example.com", "password": "password1", "display_name": "VM"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 1440,
            "governor_confidence_min": 0.75,
            "vocabulary_alignment_requires_review": True,
        },
    )

    proposed = _mcp(
        client,
        workspace_id,
        headers,
        "upsert_vocabulary_alignment",
        {
            "source_uri": "http://example.org/m#a",
            "target_uri": "http://example.org/m#b",
            "relation": "skos:exactMatch",
            "confidence": 0.88,
        },
        rpc_id=1,
    )
    assert proposed["status"] == "proposed"
    review_item_id = proposed["review_item_id"]

    approved = _mcp(
        client,
        workspace_id,
        headers,
        "approve_review_item",
        {"item_id": review_item_id, "rationale": "mcp ok"},
        rpc_id=2,
    )
    assert approved["item"]["status"] in {"approved", "resolved"}

    listed = _mcp(
        client,
        workspace_id,
        headers,
        "list_vocabulary_alignments",
        {},
        rpc_id=3,
    )
    assert len(listed["alignments"]) >= 1


def test_sidecar_alignments_backfill_sql_on_hub_load(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-bf@example.com", "password": "password1", "display_name": "BF"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    persistence = GraphPersistence(tmp_path)
    write_alignment_sidecar(
        persistence,
        workspace_id,
        {
            "side-1": {
                "id": "side-1",
                "source_uri": "http://example.org/side#a",
                "target_uri": "http://example.org/side#b",
                "relation": "skos:exactMatch",
                "confidence": 1.0,
            }
        },
    )

    knowledge = app.state.knowledge_store
    with knowledge._lock:
        assert fetch_alignments_dict(knowledge._conn, workspace_id) == {}

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["source_uri"] == "http://example.org/side#a"

    with knowledge._lock:
        stored = fetch_alignments_dict(knowledge._conn, workspace_id)
    assert "side-1" in stored


def test_alignment_proposal_reject_via_mcp(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "valign-mcp-rej@example.com", "password": "password1", "display_name": "MR"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 1440,
            "governor_confidence_min": 0.75,
            "vocabulary_alignment_requires_review": True,
        },
    )

    proposed = _mcp(
        client,
        workspace_id,
        headers,
        "upsert_vocabulary_alignment",
        {
            "source_uri": "http://example.org/x#a",
            "target_uri": "http://example.org/x#b",
            "relation": "skos:exactMatch",
        },
        rpc_id=10,
    )
    review_item_id = proposed["review_item_id"]

    rejected = _mcp(
        client,
        workspace_id,
        headers,
        "reject_review_item",
        {"item_id": review_item_id, "rationale": "mcp no"},
        rpc_id=11,
    )
    assert rejected["item"]["status"] == "rejected"

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/alignments", headers=headers).json()
    assert listed == []
