"""MCP remember guard for read-scoped API tokens."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_mcp_read_token_cannot_propose_remember(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rd@example.com", "password": "password1", "display_name": "Rd"},
    ).json()
    session_headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session_headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session_headers,
        json={"name": "read-agent", "scope": "read"},
    ).json()
    api_headers = {"Authorization": f"Bearer {created['secret']}"}

    denied = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=api_headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "propose_remember", "arguments": {"content": "nope"}},
        },
    )
    assert denied.status_code == 200
    result = denied.json()["result"]
    assert result.get("isError") is True
