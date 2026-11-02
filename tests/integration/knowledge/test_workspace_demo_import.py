"""Workspace create with optional demo pack import."""

import pytest
from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings

pytest.importorskip("semantica")

from tests.support.demo_workspace import create_workspace_with_demo


def test_create_workspace_without_demo_is_empty(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, demo_workspace_enabled=True)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "plain@example.com", "password": "password1", "display_name": "P"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    wid = create_workspace_with_demo(client, headers, name="Empty", import_demo_data=False)
    meta = client.get(f"/api/v1/workspaces/{wid}", headers=headers).json()
    assert meta.get("document_count", 0) == 0


def test_create_workspace_import_demo_seeds_documents(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True))
    )
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "demo@example.com", "password": "password1", "display_name": "D"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    wid = create_workspace_with_demo(client, headers)
    meta = client.get(f"/api/v1/workspaces/{wid}", headers=headers).json()
    assert meta.get("document_count", 0) >= 4


def test_import_demo_rejected_when_disabled(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, demo_workspace_enabled=False)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "off@example.com", "password": "password1", "display_name": "O"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    resp = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "X", "visibility": "restricted", "import_demo_data": True},
    )
    assert resp.status_code == 403
