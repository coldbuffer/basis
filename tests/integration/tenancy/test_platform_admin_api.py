from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str, name: str = "用户") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health(tmp_path) -> None:
    response = _client(tmp_path).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_each_registration_gets_a_private_default_workspace(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com", "管理员")
    assert admin["user"]["is_admin"] is True

    admin_headers = _auth(admin["token"])
    admin_workspaces = client.get("/api/v1/workspaces", headers=admin_headers).json()["workspaces"]
    assert len(admin_workspaces) == 1
    assert admin_workspaces[0]["name"] == "默认工作区"
    assert admin_workspaces[0]["visibility"] == "restricted"
    assert admin_workspaces[0]["my_role"] == "owner"

    member = _register(client, "member@example.com", "成员")
    member_workspaces = client.get("/api/v1/workspaces", headers=_auth(member["token"])).json()["workspaces"]
    assert len(member_workspaces) == 1
    assert member_workspaces[0]["name"] == "默认工作区"
    assert member_workspaces[0]["visibility"] == "restricted"
    assert member_workspaces[0]["my_role"] == "owner"
    assert member_workspaces[0]["id"] != admin_workspaces[0]["id"]


def test_registration_switch_and_admin_provisioning(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    headers = _auth(admin["token"])
    _register(client, "editor@example.com", "编辑")

    closed = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"open_registration": False},
    )
    assert closed.status_code == 200
    assert closed.json()["open_registration"] is False

    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password1", "display_name": "新用户"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "registration_closed"

    created = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "provisioned@example.com",
            "password": "password1",
            "display_name": "代开",
            "is_admin": False,
        },
    )
    assert created.status_code == 200
    assert created.json()["user"]["is_admin"] is False


def test_cannot_deactivate_self_or_the_last_admin(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    headers = _auth(admin["token"])
    other = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "other-admin@example.com",
            "password": "password1",
            "display_name": "另一位",
            "is_admin": True,
        },
    ).json()["user"]

    self_deactivate = client.post(
        f"/api/v1/admin/users/{admin['user']['id']}/deactivate",
        headers=headers,
    )
    assert self_deactivate.status_code == 409

    assert client.post(
        f"/api/v1/admin/users/{other['id']}/deactivate", headers=headers
    ).status_code == 200
    last = client.post(
        f"/api/v1/admin/users/{admin['user']['id']}/deactivate", headers=headers
    )
    assert last.status_code == 409
    assert last.json()["detail"]["code"] == "last_admin"


def test_restricted_workspace_is_hidden_and_roles_are_enforced(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    editor = _register(client, "editor@example.com", "编辑")
    outsider = _register(client, "outsider@example.com", "外人")
    admin_headers = _auth(admin["token"])
    editor_headers = _auth(editor["token"])

    created = client.post(
        "/api/v1/workspaces",
        headers=editor_headers,
        json={"name": "合同库", "visibility": "restricted"},
    )
    assert created.status_code == 200
    workspace_id = created.json()["id"]

    outsider_list = client.get("/api/v1/workspaces", headers=_auth(outsider["token"])).json()["workspaces"]
    assert workspace_id not in {item["id"] for item in outsider_list}

    admin_list = client.get("/api/v1/workspaces", headers=admin_headers).json()["workspaces"]
    assert workspace_id in {item["id"] for item in admin_list}

    open_attempt = client.post(
        "/api/v1/workspaces",
        headers=editor_headers,
        json={"name": "公开库", "visibility": "open"},
    )
    assert open_attempt.status_code == 403

    added = client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{outsider['user']['id']}",
        headers=editor_headers,
        json={"role": "viewer"},
    )
    assert added.status_code == 200

    demote = client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{editor['user']['id']}",
        headers=editor_headers,
        json={"role": "editor"},
    )
    assert demote.status_code == 409
    assert demote.json()["detail"]["code"] == "last_owner"

    denied = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=_auth(outsider["token"]),
        json={"doc_id": "doc-1", "text": "条款"},
    )
    assert denied.status_code == 403


def test_model_settings_hide_secrets(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    editor = _register(client, "editor@example.com")
    headers = _auth(admin["token"])

    saved = client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "chat_base_url": "http://localhost:11434/v1",
            "chat_model": "qwen",
            "chat_api_key": "secret-key",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["has_chat_key"] is True
    assert "secret-key" not in saved.text

    denied = client.get("/api/v1/settings", headers=_auth(editor["token"]))
    assert denied.status_code == 403

    events = client.get("/api/v1/audit", headers=headers).json()["events"]
    assert any(event["action"] == "settings.updated" for event in events)
