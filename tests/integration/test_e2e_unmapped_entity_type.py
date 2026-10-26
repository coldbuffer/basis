"""Playwright _e2e/unmapped-entity-type helper."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.domain.knowledge.services.governor_unmapped_types import UNMAPPED_ENTITY_TYPE_KIND
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app

pytest.importorskip("semantica")


def test_e2e_unmapped_entity_type_seed_with_l1_hint(tmp_path: Path) -> None:
    e2e_root = tmp_path / "data" / "e2e"
    e2e_root.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_root)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "e2eunmap@example.com", "password": "password1", "display_name": "E2E"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/_e2e/unmapped-entity-type",
        headers=headers,
        json={"label": "e2e_label_x", "with_l1_hint": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "e2e_label_x"
    assert body["review_item_id"]
    assert body["l1_uri"] == "http://example.org/e2e#Class"

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": UNMAPPED_ENTITY_TYPE_KIND, "status": "open"},
    ).json()["items"]
    assert any(item["id"] == body["review_item_id"] for item in items)


def test_e2e_unmapped_entity_type_without_l1_hint(tmp_path: Path) -> None:
    e2e_root = tmp_path / "data" / "e2e"
    e2e_root.mkdir(parents=True)
    client = TestClient(create_app(Settings(data_dir=e2e_root)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "e2eunmap2@example.com", "password": "password1", "display_name": "E2E2"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/_e2e/unmapped-entity-type",
        headers=headers,
        json={"label": "plain_label"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["l1_uri"] is None
