"""M6 vertical-slice API smoke (alerts, rules, ingest sources, remember → review)."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))


def _headers(client: TestClient, email: str = "m6@example.com") -> dict[str, str]:
    body = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "M6"},
    ).json()
    return {"Authorization": f"Bearer {body['token']}"}


def test_m6_alerts_rules_sources_smoke(tmp_path) -> None:
    client = _client(tmp_path)
    headers = _headers(client)
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers)
    assert alerts.status_code == 200
    assert "alerts" in alerts.json()

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/rules",
        headers=headers,
        json={"name": "smoke", "body": "IF a(X) THEN b(X)", "enabled": True},
    )
    assert created.status_code == 200
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/rules", headers=headers)
    assert listed.status_code == 200
    assert any(r["name"] == "smoke" for r in listed.json()["rules"])

    sources = client.get(f"/api/v1/workspaces/{workspace_id}/sources", headers=headers)
    assert sources.status_code == 200
    assert "sources" in sources.json()

    webhook = client.post(
        f"/api/v1/workspaces/{workspace_id}/sources",
        headers=headers,
        json={"kind": "webhook", "name": "m6-hook"},
    )
    assert webhook.status_code == 200
    assert webhook.json().get("ingest_token")

    remembered = client.post(
        f"/api/v1/workspaces/{workspace_id}/remember/proposals",
        headers=headers,
        json={"content": "M6 smoke remembered fact."},
    )
    assert remembered.status_code == 200
    review_id = remembered.json()["review_item_id"]
    items = client.get(f"/api/v1/workspaces/{workspace_id}/review/items", headers=headers).json()["items"]
    assert any(i["id"] == review_id and i["kind"] == "statement_remember" for i in items)

    one = client.get(f"/api/v1/workspaces/{workspace_id}/review/items/{review_id}", headers=headers)
    assert one.status_code == 200
    assert one.json()["item"]["status"] == "open"

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{review_id}/approve",
        headers=headers,
        json={"rationale": "m6 smoke"},
    )
    assert approved.status_code == 200
    assert approved.json()["item"]["status"] == "approved"

    derived = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/derived-facts", headers=headers)
    assert derived.status_code == 200
    assert "derived_facts" in derived.json()

    ingest_jobs = client.get(f"/api/v1/workspaces/{workspace_id}/ingest/jobs", headers=headers)
    assert ingest_jobs.status_code == 200
    assert "jobs" in ingest_jobs.json()
