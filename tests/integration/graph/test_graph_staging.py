"""Graph staging manifest (F-DIFF-01)."""

from pathlib import Path

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.services.graph.reads.staging import (
    build_graph_staging_payload,
    staging_session_key,
)
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.app import create_app


def test_build_graph_staging_payload_focus_nodes() -> None:
    diff = {
        "from_time": "2020-01-01T00:00:00",
        "to_time": "2021-01-01T00:00:00",
        "added_nodes": ["a"],
        "removed_nodes": ["b"],
        "modified_nodes": [{"id": "c", "change": "properties"}],
        "summary": {
            "nodes_added": 1,
            "nodes_removed": 1,
            "nodes_modified": 1,
            "edges_added": 0,
            "edges_removed": 0,
        },
    }
    payload = build_graph_staging_payload("ws-1", diff)
    assert payload["manifest"]["change_total"] == 3
    assert payload["manifest"]["focus_node_ids"] == ["a", "c"]
    assert payload["manifest"]["governance"]["direct_merge_allowed"] is False
    assert payload["manifest"]["session_key"] == staging_session_key(
        "ws-1", "2020-01-01T00:00:00", "2021-01-01T00:00:00"
    )


def test_staging_session_key_stable() -> None:
    a = staging_session_key("ws-a", "2020-01-01", "2021-01-01")
    b = staging_session_key("ws-a", "2020-01-01", "2021-01-01")
    c = staging_session_key("ws-a", "2020-01-02", "2021-01-01")
    assert a == b
    assert a != c
    assert len(a) == 16


def test_graph_staging_route_after_ingest(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "stg@example.com", "password": "password1", "display_name": "Stg"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "s1", "text": "Ivy knows Jake.", "wait": True, "extract": True},
    )

    staging = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/staging",
        headers=headers,
        params={"from": "2020-01-01T00:00:00", "to": "2030-01-01T00:00:00"},
    )
    assert staging.status_code == 200
    body = staging.json()
    assert body.get("workspace_id") == workspace_id
    assert "manifest" in body and "diff" in body
    assert body["manifest"].get("session_key")
    assert body["manifest"]["governance"]["entity_merge_proposal_relpath"] == (
        "graph/staging/entity-merge"
    )
    skey = body["manifest"]["session_key"]

    put_draft = client.put(
        f"/api/v1/workspaces/{workspace_id}/graph/staging/{skey}/draft",
        headers=headers,
        json={
            "from_time": "2020-01-01T00:00:00",
            "to_time": "2030-01-01T00:00:00",
            "primary": "ent_primary",
            "duplicate": "ent_dup",
        },
    )
    assert put_draft.status_code == 200
    assert put_draft.json()["draft"] == {"primary": "ent_primary", "duplicate": "ent_dup"}

    staging_again = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/staging",
        headers=headers,
        params={"from": "2020-01-01T00:00:00", "to": "2030-01-01T00:00:00"},
    )
    assert staging_again.status_code == 200
    assert staging_again.json()["manifest"]["draft"] == {
        "primary": "ent_primary",
        "duplicate": "ent_dup",
    }
