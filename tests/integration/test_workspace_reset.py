"""Workspace reset keeps shell; clears ledger."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def _session(tmp_path: Path) -> tuple[TestClient, str, dict[str, str], str]:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "reset@example.com", "password": "password1", "display_name": "R"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspaces = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"]
    workspace = workspaces[0]
    return client, workspace["id"], headers, workspace["name"]


def test_workspace_reset_http_and_mcp_preview(tmp_path: Path) -> None:
    client, workspace_id, headers, workspace_name = _session(tmp_path)
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "reset-doc", "text": "To be cleared."},
    )
    assert created.status_code == 200

    preview = client.get(f"/api/v1/workspaces/{workspace_id}/reset", headers=headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["preview"] is True
    assert body["counts"]["document_count"] >= 1

    bad = client.post(
        f"/api/v1/workspaces/{workspace_id}/reset",
        headers=headers,
        json={"confirmation": "wrong-name"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "confirmation_required"

    ok = client.post(
        f"/api/v1/workspaces/{workspace_id}/reset",
        headers=headers,
        json={"confirmation": workspace_name, "async": False},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    assert ok.json()["cleared"]["document_count"] >= 1

    still = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert still.status_code == 200
    assert still.json()["id"] == workspace_id
    assert still.json()["document_count"] == 0
    assert still.json()["entity_count"] == 0

    mcp_preview = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "reset_workspace", "arguments": {"preview": True}},
        },
    ).json()
    counts = json.loads(mcp_preview["result"]["content"][0]["text"])["counts"]
    assert counts["document_count"] == 0


def test_workspace_reset_async_job(tmp_path: Path) -> None:
    import time

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "reset-async@example.com", "password": "password1", "display_name": "A"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    name = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers).json()["name"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "async-reset", "text": "x"},
    )
    accepted = client.post(
        f"/api/v1/workspaces/{workspace_id}/reset",
        headers=headers,
        json={"confirmation": name, "async": True},
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body.get("accepted") is True
    job_id = body["job_id"]
    status = "queued"
    for _ in range(120):
        job = client.get(f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{job_id}", headers=headers)
        assert job.status_code == 200
        payload = job.json()["job"]
        status = payload["status"]
        if status in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert status == "succeeded"
    assert job.json()["job"]["kind"] == "workspace_reset"


def test_workspace_reset_connectors_scope_keeps_documents(tmp_path: Path) -> None:
    client, workspace_id, headers, workspace_name = _session(tmp_path)
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "scope-keep-doc", "text": "Stay."},
    )
    assert created.status_code == 200

    preview = client.get(f"/api/v1/workspaces/{workspace_id}/reset", headers=headers)
    assert preview.status_code == 200
    assert "default_scopes" in preview.json()
    assert preview.json()["export_pack_path"].endswith("/graph?export=1")

    ok = client.post(
        f"/api/v1/workspaces/{workspace_id}/reset",
        headers=headers,
        json={
            "confirmation": workspace_name,
            "async": False,
            "scopes": ["connectors"],
        },
    )
    assert ok.status_code == 200
    assert ok.json()["scopes"] == ["connectors"]

    still = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert still.json()["document_count"] == 1

    bad_scopes = client.post(
        f"/api/v1/workspaces/{workspace_id}/reset",
        headers=headers,
        json={"confirmation": workspace_name, "async": False, "scopes": ["nope"]},
    )
    assert bad_scopes.status_code == 422
    assert bad_scopes.json()["detail"]["code"] == "invalid_scopes"


def test_workspace_reset_mcp_async_job(tmp_path: Path) -> None:
    import time

    client, workspace_id, headers, workspace_name = _session(tmp_path)
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "mcp-async", "text": "gone"},
    )
    accepted = client.post(
        f"/api/v1/workspaces/{workspace_id}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "reset_workspace",
                "arguments": {
                    "confirmation": workspace_name,
                    "async": True,
                    "scopes": ["knowledge", "graph"],
                },
            },
        },
    ).json()
    payload = json.loads(accepted["result"]["content"][0]["text"])
    assert payload.get("accepted") is True
    job_id = payload["job_id"]
    status = "queued"
    for _ in range(120):
        job = client.get(f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{job_id}", headers=headers)
        status = job.json()["job"]["status"]
        if status in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert status == "succeeded"
    assert client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers).json()["document_count"] == 0
