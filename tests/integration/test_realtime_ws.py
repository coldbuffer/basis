from io import BytesIO

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_realtime_ticket_and_websocket_connect(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ws@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    ticket_resp = client.post(f"/api/v1/workspaces/{workspace_id}/realtime-ticket", headers=headers)
    assert ticket_resp.status_code == 200
    ticket = ticket_resp.json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}"
    ) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"
        assert hello["workspace_id"] == workspace_id

    reuse = client.websocket_connect(f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}")
    with pytest.raises(Exception):
        with reuse:
            reuse.receive_json()


def test_rebuild_emits_projection_updated_when_http_handler_uses_thread_pool(tmp_path) -> None:
    """Rebuild runs in asyncio.to_thread; broadcast must use the main event loop."""
    from concurrent.futures import ThreadPoolExecutor

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "wspool@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    ticket = client.post(f"/api/v1/workspaces/{workspace_id}/realtime-ticket", headers=headers).json()["ticket"]

    with client.websocket_connect(f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "connected"
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                client.post,
                f"/api/v1/workspaces/{workspace_id}/graph/rebuild",
                headers=headers,
            )
            assert future.result().status_code == 200
        event = ws.receive_json()
        assert event["type"] == "projection_updated"
        assert event["workspace_id"] == workspace_id


def test_rebuild_emits_projection_updated_on_websocket(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "wsb@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    ticket = client.post(f"/api/v1/workspaces/{workspace_id}/realtime-ticket", headers=headers).json()["ticket"]

    with client.websocket_connect(f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "connected"
        client.post(
            f"/api/v1/workspaces/{workspace_id}/documents",
            headers=headers,
            json={"doc_id": "ws-doc", "text": "x", "extract": False},
        )
        assert client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers).status_code == 200
        event = ws.receive_json()
        assert event["type"] == "projection_updated"
        assert event["workspace_id"] == workspace_id


def test_ingest_emits_projection_updated_on_websocket(tmp_path) -> None:
    """M5 — inline ingest completion should notify graph subscribers."""
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "wsc@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    ticket = client.post(f"/api/v1/workspaces/{workspace_id}/realtime-ticket", headers=headers).json()["ticket"]

    with client.websocket_connect(f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "connected"
        uploaded = client.post(
            f"/api/v1/workspaces/{workspace_id}/documents/upload",
            headers=headers,
            files={"file": ("rt.txt", BytesIO(b"realtime ingest body"), "text/plain")},
            data={"extract": "false", "wait": "true"},
        )
        assert uploaded.status_code == 200
        event = ws.receive_json()
        assert event["type"] == "projection_updated"
        assert event["workspace_id"] == workspace_id
        assert isinstance(event.get("projection_revision"), int)


def test_wrong_workspace_ticket_rejected(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "w2@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    other = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    ticket = client.post(f"/api/v1/workspaces/{workspace_id}/realtime-ticket", headers=headers).json()["ticket"]
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/workspaces/{other}/ws/graph-updates?ticket={ticket}"):
            pass


def test_member_removed_revokes_open_websocket(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    owner = client.post(
        "/api/v1/auth/register",
        json={"email": "own@example.com", "password": "password1", "display_name": "Owner"},
    ).json()
    member = client.post(
        "/api/v1/auth/register",
        json={"email": "mem@example.com", "password": "password1", "display_name": "Member"},
    ).json()
    owner_headers = _auth(owner["token"])
    member_headers = _auth(member["token"])
    member_id = member["user"]["id"]

    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Team", "visibility": "restricted"},
    ).json()["id"]
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "viewer"},
    )

    ticket = client.post(
        f"/api/v1/workspaces/{workspace_id}/realtime-ticket",
        headers=member_headers,
    ).json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}"
    ) as ws:
        assert ws.receive_json()["type"] == "connected"
        removed = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
            headers=owner_headers,
        )
        assert removed.status_code == 200
        revoked = ws.receive_json()
        assert revoked["type"] == "access_revoked"
        assert revoked["workspace_id"] == workspace_id


def test_member_role_change_revokes_websocket(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    owner = client.post(
        "/api/v1/auth/register",
        json={"email": "own2@example.com", "password": "password1", "display_name": "Owner"},
    ).json()
    member = client.post(
        "/api/v1/auth/register",
        json={"email": "mem2@example.com", "password": "password1", "display_name": "Member"},
    ).json()
    owner_headers = _auth(owner["token"])
    member_headers = _auth(member["token"])
    member_id = member["user"]["id"]

    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Role KB", "visibility": "restricted"},
    ).json()["id"]
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "editor"},
    )

    ticket = client.post(
        f"/api/v1/workspaces/{workspace_id}/realtime-ticket",
        headers=member_headers,
    ).json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}"
    ) as ws:
        assert ws.receive_json()["type"] == "connected"
        changed = client.put(
            f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
            headers=owner_headers,
            json={"role": "viewer"},
        )
        assert changed.status_code == 200
        revoked = ws.receive_json()
        assert revoked["type"] == "access_revoked"
        assert revoked["workspace_id"] == workspace_id


def test_deactivate_user_revokes_all_websockets(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "adm@example.com", "password": "password1", "display_name": "Admin"},
    ).json()
    member = client.post(
        "/api/v1/auth/register",
        json={"email": "deact@example.com", "password": "password1", "display_name": "Gone"},
    ).json()
    admin_headers = _auth(admin["token"])
    member_headers = _auth(member["token"])
    member_id = member["user"]["id"]

    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=admin_headers,
        json={"name": "Shared", "visibility": "restricted"},
    ).json()["id"]
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=admin_headers,
        json={"role": "viewer"},
    )

    ticket = client.post(
        f"/api/v1/workspaces/{workspace_id}/realtime-ticket",
        headers=member_headers,
    ).json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/workspaces/{workspace_id}/ws/graph-updates?ticket={ticket}"
    ) as ws:
        assert ws.receive_json()["type"] == "connected"
        deactivated = client.post(
            f"/api/v1/admin/users/{member_id}/deactivate",
            headers=admin_headers,
        )
        assert deactivated.status_code == 200
        revoked = ws.receive_json()
        assert revoked["type"] == "access_revoked"
        assert revoked.get("reason") == "user_deactivated"
