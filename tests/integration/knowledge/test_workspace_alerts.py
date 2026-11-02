"""Workspace alert episodes (F-ALT MVP)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _test_settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, ingest_inline=True)


def test_sync_failure_emits_alert(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "alt@example.com", "password": "password1", "display_name": "Alt"},
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
    source_id = created.json()["source"]["id"]

    mock_http = MagicMock()
    mock_http.get.side_effect = RuntimeError("connection reset")
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)

    with patch(
        "basis.services.knowledge.services.ingest_source_service.httpx.Client", return_value=mock_http
    ):
        failed = client.post(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}/sync", headers=headers, json={})
    assert failed.status_code >= 400

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["unread_count"] >= 1
    alerts = body["alerts"]
    assert any(a["kind"] == "sync_failed" for a in alerts)
    alert_id = next(a["id"] for a in alerts if a["kind"] == "sync_failed")

    dismissed = client.post(
        f"/api/v1/workspaces/{workspace_id}/alerts/{alert_id}/dismiss",
        headers=headers,
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["alert"]["dismissed_at"]

    after = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers)
    after_body = after.json()
    assert all(a["id"] != alert_id for a in after_body["alerts"])
    assert after_body["unread_count"] == 0


def test_mark_all_read_clears_unread_but_keeps_list(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "read@example.com", "password": "password1", "display_name": "Read"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store
    knowledge.create_workspace_alert(workspace_id, kind="sync_failed", message="Unread")

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()
    assert listed["unread_count"] == 1
    assert len(listed["alerts"]) == 1

    marked = client.post(f"/api/v1/workspaces/{workspace_id}/alerts/mark-all-read", headers=headers)
    assert marked.status_code == 200
    body = marked.json()
    assert body["marked_read_count"] == 1
    assert body["unread_count"] == 0

    after = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()
    assert len(after["alerts"]) == 1
    assert after["unread_count"] == 0
    assert after["alerts"][0]["read_at"]


def test_dismiss_all_alerts(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "dall@example.com", "password": "password1", "display_name": "Dall"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store
    knowledge.create_workspace_alert(workspace_id, kind="sync_failed", message="One")
    knowledge.create_workspace_alert(workspace_id, kind="sync_failed", message="Two")

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()
    assert listed["unread_count"] == 2

    bulk = client.post(f"/api/v1/workspaces/{workspace_id}/alerts/dismiss-all", headers=headers)
    assert bulk.status_code == 200
    body = bulk.json()
    assert body["dismissed_count"] == 2
    assert body["unread_count"] == 0

    after = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()
    assert after["alerts"] == []
    assert after["unread_count"] == 0


def test_alerts_workspace_isolation(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    a = client.post(
        "/api/v1/auth/register",
        json={"email": "iso-alt@example.com", "password": "password1", "display_name": "Iso"},
    ).json()
    headers = {"Authorization": f"Bearer {a['token']}"}
    workspace_a = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Private alerts", "visibility": "restricted"},
    ).json()["id"]
    workspace_b = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "stranger@example.com", "password": "password1", "display_name": "Str"},
    ).json()
    headers_b = {"Authorization": f"Bearer {other['token']}"}

    denied = client.get(f"/api/v1/workspaces/{workspace_a}/alerts", headers=headers_b)
    assert denied.status_code == 403

    ok_b = client.get(f"/api/v1/workspaces/{workspace_b}/alerts", headers=headers)
    assert ok_b.status_code == 200


def test_list_alerts_since_skips_at_or_before_cursor(tmp_path) -> None:
    client = TestClient(create_app(_test_settings(tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "since@example.com", "password": "password1", "display_name": "Since"},
    ).json()
    workspace_id = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {admin['token']}"},
    ).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store
    first = knowledge.create_workspace_alert(workspace_id, kind="sync_failed", message="First")
    second = knowledge.create_workspace_alert(workspace_id, kind="sync_failed", message="Second")
    after_first = knowledge.list_alerts_since(
        workspace_id,
        since_created_at=first["created_at"],
    )
    ids = {a["id"] for a in after_first}
    assert first["id"] not in ids
    assert second["id"] in ids
