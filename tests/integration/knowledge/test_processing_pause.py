"""Pause, checkpoint resume, and restart recovery for document ingest jobs."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.knowledge.pipeline.ingest_control import request_ingest_pause


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str], str]:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "pause@example.com", "password": "password1", "display_name": "Pause"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, headers, workspace_id


def _upload(client: TestClient, headers: dict[str, str], workspace_id: str, text: str) -> dict:
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "pause-doc", "text": text},
    )
    assert uploaded.status_code == 200
    return uploaded.json()


def test_pause_queued_job_unblocks_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "basis.routes.workspace.knowledge.documents.ingest_helpers.enqueue_version_ingest",
        lambda *args, **kwargs: None,
    )
    client, headers, workspace_id = _client(tmp_path)
    source = _upload(client, headers, workspace_id, "Alice knows Bob.")
    started = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "wait": False,
            "chunk": False,
            "extract": False,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    paused = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}/pause",
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["pause_requested"] is False

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs?status=paused",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["id"] == job_id

    denied = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}/pause",
        headers=headers,
    )
    assert denied.status_code == 200
    assert denied.json()["status"] == "paused"

    deleted = client.delete(
        f"/api/v1/workspaces/{workspace_id}/documents/{source['document_id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_pause_during_extract_resumes_remaining_chunks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "basis.services.knowledge.pipeline.extract_kwargs.validate_extract_options",
        lambda *args, **kwargs: None,
    )
    calls = {"n": 0}

    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "resume@example.com", "password": "password1", "display_name": "Resume"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    def fake_build(doc_id: str, text: str, options, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            jobs = app.state.knowledge_store.list_processing_jobs(workspace_id)
            request_ingest_pause(jobs[0]["id"])
        return {"entities": [], "relationships": []}

    monkeypatch.setattr(
        "basis.services.knowledge.pipeline.version_ingest.build_kg_from_text",
        fake_build,
    )
    text = "Alice met Bob at the harbor. " * 40
    source = _upload(client, headers, workspace_id, text)
    paused = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "wait": True,
            "chunk": True,
            "chunk_size": 400,
            "chunk_overlap": 50,
            "extract": True,
            "ner_method": "llm",
            "relation_method": "llm",
            "llm_model": "test-model",
        },
    )
    assert paused.status_code == 200
    body = paused.json()
    assert body["status"] == "paused"
    checkpoint = body["checkpoint"]
    assert checkpoint["chunk_count"] >= 2
    assert len(checkpoint["completed_chunk_ids"]) == 1
    assert calls["n"] == 1
    job_id = body["job_id"]

    detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{job_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["job"]["status"] == "paused"
    assert detail.json()["job"]["attempt"] == 1
    assert detail.json()["version"]["status"] == "paused"

    resumed = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}/resume",
        headers=headers,
        json={"wait": True},
    )
    assert resumed.status_code == 200
    assert resumed.json()["ledger_status"] == "ready"
    assert calls["n"] == checkpoint["chunk_count"]

    finished = client.get(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}",
        headers=headers,
    ).json()["job"]
    assert finished["status"] == "succeeded"
    assert finished["attempt"] == 1


def test_restart_pauses_orphaned_running_job_and_allows_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "basis.routes.workspace.knowledge.documents.ingest_helpers.enqueue_version_ingest",
        lambda *args, **kwargs: None,
    )
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        admin = client.post(
            "/api/v1/auth/register",
            json={"email": "orphan@example.com", "password": "password1", "display_name": "Orphan"},
        ).json()
        headers = _auth(admin["token"])
        workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
        source = _upload(client, headers, workspace_id, "A note that was still extracting.")
        started = client.post(
            f"/api/v1/workspaces/{workspace_id}/processing/jobs",
            headers=headers,
            json={
                "version_id": source["version_id"],
                "wait": False,
                "chunk": False,
                "extract": False,
                "ner_method": "llm",
                "relation_method": "llm",
            },
        )
        assert started.status_code == 202
        job_id = started.json()["job_id"]
        knowledge = app.state.knowledge_store
        knowledge.set_job_status(workspace_id, job_id, "running")
        knowledge.set_version_status(workspace_id, source["version_id"], "extracting")
        busy = client.delete(
            f"/api/v1/workspaces/{workspace_id}/documents/{source['document_id']}",
            headers=headers,
        )
        assert busy.status_code == 409

    restarted = create_app(Settings(data_dir=tmp_path))
    with TestClient(restarted) as client:
        admin = client.post(
            "/api/v1/auth/login",
            json={"email": "orphan@example.com", "password": "password1"},
        ).json()
        headers = _auth(admin["token"])
        detail = client.get(
            f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{job_id}",
            headers=headers,
        )
        assert detail.status_code == 200
        assert detail.json()["job"]["status"] == "paused"
        assert detail.json()["version"]["status"] == "paused"
        deleted = client.delete(
            f"/api/v1/workspaces/{workspace_id}/documents/{source['document_id']}",
            headers=headers,
        )
        assert deleted.status_code == 200


def test_pause_rejects_finished_job(tmp_path: Path) -> None:
    client, headers, workspace_id = _client(tmp_path)
    source = _upload(client, headers, workspace_id, "Already done.")
    done = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "wait": True,
            "chunk": False,
            "extract": False,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert done.status_code == 200
    job_id = done.json()["job_id"]
    paused = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}/pause",
        headers=headers,
    )
    assert paused.status_code == 409
    assert paused.json()["detail"]["code"] == "job_not_pausable"
