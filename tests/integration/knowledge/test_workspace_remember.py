"""Chat/MCP remember → review queue (F-CHAT-04)."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_chat_remember_creates_pending_review(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "mem@example.com", "password": "password1", "display_name": "Mem"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Remember KB", "visibility": "restricted"},
    ).json()["id"]

    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": "Acme Corp was founded in 2010."},
    )
    assert proposed.status_code == 200
    review_id = proposed.json()["review_item_id"]

    items = client.get(f"/api/v1/workspaces/{workspace_id}/review/items", headers=headers).json()["items"]
    assert any(i["id"] == review_id and i["kind"] == "statement_remember" for i in items)

    fetched = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items/{review_id}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["item"]["id"] == review_id
    assert fetched.json()["item"]["status"] == "open"

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{review_id}/approve",
        headers=headers,
        json={"rationale": "looks good"},
    )
    assert approved.status_code == 200
    assert "decision_id" in approved.json()
    statement_id = proposed.json()["statement_id"]
    assert approved.json()["merge"]["statement_id"] == statement_id
