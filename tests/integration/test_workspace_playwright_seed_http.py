"""HTTP integration: workspace `/_e2e/*` seed routes (gated on `data/e2e`)."""

from pathlib import Path

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def test_playwright_governance_trip_disabled_outside_data_dir(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e@example.com", "password": "password1", "display_name": "E2E"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    res = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/governance-trip", headers=headers)
    assert res.status_code == 404


def test_playwright_governance_trip_records_alert_and_decision(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_dir)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e2@example.com", "password": "password1", "display_name": "E2E2"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    trip = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/governance-trip", headers=headers)
    assert trip.status_code == 200
    decision_id = trip.json().get("decision_id")
    assert isinstance(decision_id, str) and decision_id

    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()["alerts"]
    tripped = [a for a in alerts if a["kind"] == "governance.tripped"]
    assert tripped
    assert tripped[0]["detail"].get("decision_id") == decision_id


def test_playwright_shacl_violation_disabled_outside_data_dir(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "sc@example.com", "password": "password1", "display_name": "SC"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    res = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/shacl-violation", headers=headers)
    assert res.status_code == 404


def test_playwright_shacl_violation_creates_review_item(tmp_path) -> None:
    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_dir)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "sc2@example.com", "password": "password1", "display_name": "SC2"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/shacl-violation", headers=headers)
    assert seeded.status_code == 200
    body = seeded.json()
    assert body.get("review_item_id")
    surface = body.get("surface_phrase")
    assert isinstance(surface, str) and surface

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": "shacl_violation"},
    ).json()["items"]
    assert any(i["id"] == body["review_item_id"] for i in items)


def test_playwright_ontology_proposal_disabled_outside_data_dir(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "op@example.com", "password": "password1", "display_name": "OP"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    res = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    assert res.status_code == 404


def test_playwright_ontology_proposal_seeds_proposed_change(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    e2e_dir = tmp_path / "data" / "e2e"
    e2e_dir.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_dir)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "op2@example.com", "password": "password1", "display_name": "OP2"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    seeded = client.post(f"/api/v1/workspaces/{workspace_id}/_e2e/ontology-proposal", headers=headers)
    assert seeded.status_code == 200
    body = seeded.json()
    proposal_id = body.get("proposal_id")
    assert isinstance(proposal_id, str) and proposal_id

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/proposals", headers=headers)
    assert listed.status_code == 200
    proposals = listed.json()
    assert any(p.get("proposal_id") == proposal_id for p in proposals)
