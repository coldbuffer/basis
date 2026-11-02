"""HTTP integration: `POST /api/v1/_e2e/playwright-reset` (Playwright data dir only)."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_playwright_reset_allows_bootstrap_admin(tmp_path) -> None:
    data_dir = tmp_path / "data" / "e2e"
    client = TestClient(create_app(Settings(data_dir=data_dir)))
    assert client.post("/api/v1/_e2e/playwright-reset").status_code == 200
    first = client.post(
        "/api/v1/auth/register",
        json={"email": "first@e2e.invalid", "password": "password1xy", "display_name": "First"},
    ).json()
    assert first["user"]["is_admin"] is True
    assert client.post("/api/v1/_e2e/playwright-reset").status_code == 200
    second = client.post(
        "/api/v1/auth/register",
        json={"email": "second@e2e.invalid", "password": "password1xy", "display_name": "Second"},
    ).json()
    assert second["user"]["is_admin"] is True


def test_playwright_reset_disabled_outside_data_e2e(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "other")))
    assert client.post("/api/v1/_e2e/playwright-reset").status_code == 404
