"""Workspace review queue for entity merge proposals."""

from unittest.mock import patch

import pytest

pytest.importorskip("semantica")

from fastapi import HTTPException
from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def test_entity_merge_review_propose_list_reject(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rev@example.com", "password": "password1", "display_name": "Rev"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/entity-merge",
        headers=headers,
        json={"primary_id": "node-a", "duplicate_ids": ["node-b"]},
    )
    assert proposed.status_code == 200
    item = proposed.json()["item"]
    assert item["kind"] == "entity_merge"
    assert item["status"] == "open"

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/review/items", headers=headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] >= 1
    assert listed_body["has_more"] is False
    assert any(row["id"] == item["id"] for row in listed_body["items"])

    rejected = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item['id']}/reject",
        headers=headers,
        json={"rationale": "not duplicates"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["item"]["status"] == "rejected"

    audit = client.get(f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations", headers=headers)
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()["events"]]
    assert "workspace.graph.merge_proposed" in actions
    assert "workspace.graph.merge_rejected" in actions


def test_direct_enrich_merge_blocked(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "blk@example.com", "password": "password1", "display_name": "Blk"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    blocked = client.post(
        f"/api/v1/workspaces/{workspace_id}/enrich/merge",
        headers=headers,
        json={"primary_id": "a", "duplicate_ids": ["b"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "merge_requires_review"


def test_review_approve_failure_emits_governance_alert(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gov-rev@example.com", "password": "password1", "display_name": "GovRev"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/entity-merge",
        headers=headers,
        json={"primary_id": "node-a", "duplicate_ids": ["node-b"]},
    ).json()["item"]

    def fail_merge(*_args, **_kwargs):
        from basis.domain.tenancy.admin.errors import AdminError

        raise AdminError(422, "impact_gate", "blocked")

    with patch(
        "basis.domain.knowledge.services.review_resolve_approve.merge_nodes",
        side_effect=fail_merge,
    ):
        failed = client.post(
            f"/api/v1/workspaces/{workspace_id}/review/items/{proposed['id']}/approve",
            headers=headers,
            json={"rationale": "try merge"},
        )
    assert failed.status_code == 422

    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()["alerts"]
    tripped = [a for a in alerts if a["kind"] == "governance.tripped"]
    assert tripped
    assert any(
        isinstance((a.get("detail") or {}).get("decision_id"), str)
        and (a.get("detail") or {})["decision_id"]
        for a in tripped
    )


def test_review_items_list_pagination(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "page@example.com", "password": "password1", "display_name": "Page"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    for i in range(3):
        resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/review/items/entity-merge",
            headers=headers,
            json={"primary_id": f"node-p-{i}", "duplicate_ids": [f"node-d-{i}"]},
        )
        assert resp.status_code == 200

    page0 = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"limit": 2, "offset": 0},
    ).json()
    assert page0["total"] == 3
    assert len(page0["items"]) == 2
    assert page0["has_more"] is True

    page1 = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"limit": 2, "offset": 2},
    ).json()
    assert len(page1["items"]) == 1
    assert page1["has_more"] is False
