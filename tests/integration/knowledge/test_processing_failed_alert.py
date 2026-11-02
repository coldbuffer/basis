"""Processing job failure emits workspace alert with job_id (F-ALT / F-SRC-08)."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_fail_job_emits_processing_failed_alert(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "pf@example.com", "password": "password1", "display_name": "PF"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store

    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "fail-doc", "text": "x", "wait": False, "extract": False},
    ).json()
    job, _ = knowledge.create_processing_job(
        workspace_id,
        version_id=source["version_id"],
        options={"chunk": False, "extract": False},
    )
    knowledge.fail_job(workspace_id, job["id"], "parse_failed", "bad file")

    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()["alerts"]
    match = next((a for a in alerts if a["kind"] == "processing.failed"), None)
    assert match is not None
    assert match["detail"]["job_id"] == job["id"]
    assert match["detail"]["error_code"] == "parse_failed"
