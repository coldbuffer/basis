"""Desktop deployment profile (ADR 0004 Phase A)."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app


def test_desktop_allows_workspaces_without_bearer(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        deployment_profile="desktop",
        host="127.0.0.1",
        port=8090,
    )
    client = TestClient(create_app(settings))
    res = client.get("/api/v1/workspaces")
    assert res.status_code == 200
    body = res.json()
    assert "workspaces" in body
    assert len(body["workspaces"]) >= 1


def test_desktop_session_issues_token(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        deployment_profile="desktop",
        host="127.0.0.1",
    )
    client = TestClient(create_app(settings))
    res = client.post("/api/v1/auth/desktop-session")
    assert res.status_code == 200
    payload = res.json()
    assert payload["token"]
    assert payload["user"]["email"] == "local@basis.desktop"


def test_server_profile_still_requires_auth(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert client.get("/api/v1/workspaces").status_code == 401


def test_desktop_rejects_non_loopback(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        deployment_profile="desktop",
        host="0.0.0.0",
    )
    try:
        create_app(settings)
        raise AssertionError("expected startup failure")
    except SystemExit:
        pass
