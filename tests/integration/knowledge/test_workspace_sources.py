"""Workspace ingest source connectors."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _test_settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, ingest_inline=True)


def test_webhook_source_crud_and_ingest(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "src@example.com", "password": "password1", "display_name": "Src"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={"kind": "webhook", "name": "HR feed"},
    )
    assert created.status_code == 200
    body = created.json()
    source_id = body["source"]["id"]
    token = body["ingest_token"]
    assert token
    assert f"/sources/{source_id}/webhook" in body["webhook_path"]

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/sources", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == source_id for s in listed.json()["sources"])

    bad = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/webhook",
        json={"text": "hello"},
    )
    assert bad.status_code == 401

    ingested = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/webhook",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Note", "text": "Webhook body", "external_key": "wh-1"},
    )
    assert ingested.status_code == 200
    assert ingested.json()["doc_id"] == "wh-1"
    assert ingested.json()["status"] == "queued"

    disabled = client.patch(
        f"/api/v1/workspaces/{workspace_id}/sources/{source_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200

    blocked = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/webhook",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "nope"},
    )
    assert blocked.status_code == 403


def test_sources_workspace_isolation(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    a = client.post(
        "/api/v1/auth/register",
        json={"email": "iso@example.com", "password": "password1", "display_name": "Iso"},
    ).json()
    headers = {"Authorization": f"Bearer {a['token']}"}
    workspace_a = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    workspace_b = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_a}/sources",
        headers=headers,
        json={"kind": "webhook", "name": "A only"},
    ).json()
    source_id = created["source"]["id"]

    denied = client.get(f"/api/v1/workspaces/{workspace_b}/sources/{source_id}", headers=headers)
    assert denied.status_code == 404


def test_ingest_source_audit_never_contains_token(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "aud@example.com", "password": "password1", "display_name": "Aud"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={"kind": "webhook", "name": "Audit"},
    )
    assert created.status_code == 200
    token = created.json()["ingest_token"]
    source_id = created.json()["source"]["id"]

    rotated = client.post(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/rotate-token", headers=headers)
    assert rotated.status_code == 200
    new_token = rotated.json()["ingest_token"]

    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations?action_prefix=workspace.ingest_source.",
        headers=headers,
    )
    assert audit.status_code == 200
    blob = str(audit.json())
    assert token not in blob
    assert new_token not in blob
    actions = [e["action"] for e in audit.json()["events"]]
    assert "workspace.ingest_source.created" in actions
    assert "workspace.ingest_source.token_rotated" in actions


def test_webhook_token_rotation(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rot@example.com", "password": "password1", "display_name": "Rot"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={"kind": "webhook", "name": "Rot"},
    ).json()
    source_id = created["source"]["id"]
    old_token = created["ingest_token"]

    rotated = client.post(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/rotate-token", headers=headers)
    assert rotated.status_code == 200
    new_token = rotated.json()["ingest_token"]
    assert new_token != old_token

    assert (
        client.post(
            f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/webhook",
            headers={"Authorization": f"Bearer {old_token}"},
            json={"text": "x"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/webhook",
            headers={"Authorization": f"Bearer {new_token}"},
            json={"text": "ok"},
        ).status_code
        == 200
    )


def test_http_poll_sync(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "poll@example.com", "password": "password1", "display_name": "Poll"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={
            "kind": "http_poll",
            "name": "Feed",
            "config": {"url": "https://example.com/feed.txt"},
        },
    )
    assert created.status_code == 200
    source_id = created.json()["source"]["id"]

    mock_response = MagicMock()
    mock_response.content = b"Poll document body"
    mock_response.encoding = "utf-8"
    mock_response.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)

    with patch("basis.services.knowledge.services.ingest_source_service.httpx.Client", return_value=mock_http):
        synced = client.post(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/sync", headers=headers, json={})

    assert synced.status_code == 200
    assert synced.json()["result"]["status"] == "queued"

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}", headers=headers).json()["source"]
    events = detail["config"].get("sync_events") or []
    assert events and events[0]["status"] == "succeeded"

    history = client.get(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/sync-history", headers=headers)
    assert history.status_code == 200
    hist = history.json()
    assert hist["source_id"] == source_id
    assert hist["events"][0]["status"] == "succeeded"


def test_git_source_sync(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "git@example.com", "password": "password1", "display_name": "Git"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={
            "kind": "git",
            "name": "Docs repo",
            "config": {
                "repo_url": "https://github.com/org/repo",
                "branch": "main",
                "paths": ["README.md"],
            },
        },
    )
    assert created.status_code == 200
    source_id = created.json()["source"]["id"]

    mock_response = MagicMock()
    mock_response.content = b"# Hello from git"
    mock_response.encoding = "utf-8"
    mock_response.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)

    with patch("basis.services.knowledge.services.ingest_source_service.httpx.Client", return_value=mock_http):
        synced = client.post(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/sync", headers=headers, json={})

    assert synced.status_code == 200
    mock_http.get.assert_called_once()
    called_url = mock_http.get.call_args[0][0]
    assert "raw.githubusercontent.com/org/repo/main/README.md" in called_url

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}", headers=headers).json()["source"]
    assert detail["config"]["sync_events"][0]["status"] == "succeeded"
    assert detail["config"]["sync_events"][0]["mode"] == "git"
