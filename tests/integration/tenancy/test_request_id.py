"""X-02 request correlation IDs."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_health_returns_request_id_header(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.get("/health")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID") or response.headers.get("x-request-id")
    assert rid
    assert len(rid) >= 16


def test_client_may_supply_request_id(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.get("/health", headers={"X-Request-ID": "client-trace-abc"})
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID") or response.headers.get("x-request-id")
    assert rid == "client-trace-abc"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_graph_rebuild_audit_includes_request_id(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "aud@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    trace = "rebuild-audit-trace"

    client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/rebuild",
        headers={**headers, "X-Request-ID": trace},
    )

    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations?action_prefix=workspace.graph.",
        headers=headers,
    )
    assert audit.status_code == 200
    events = audit.json()["events"]
    rebuild = next(
        e for e in events if e["action"] == "workspace.graph.projection_rebuild"
    )
    assert rebuild["detail"]["request_id"] == trace


def test_unauthorized_includes_request_id_in_detail(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.get(
        "/api/v1/workspaces",
        headers={"X-Request-ID": "auth-fail-1"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["request_id"] == "auth-fail-1"
    assert detail.get("code") == "unauthorized"
