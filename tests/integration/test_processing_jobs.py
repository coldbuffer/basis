"""Separated source upload and explicit processing jobs."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_upload_then_process_with_immutable_options(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "password1", "display_name": "Flow"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "source-only", "text": "Alice knows Bob."},
    )
    assert uploaded.status_code == 200
    source = uploaded.json()
    assert source["status"] == "uploaded"

    before = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers)
    assert before.status_code == 200
    assert before.json()["jobs"] == []

    processed = client.post(
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
    assert processed.status_code == 200
    assert processed.json()["ledger_status"] == "ready"

    jobs = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers).json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["status"] == "succeeded"
    assert jobs[0]["options"]["chunk"] is False
    assert jobs[0]["options"]["extract"] is False
    assert jobs[0]["result"]["ledger_status"] == "ready"


def test_processing_job_persists_request_id_in_options(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rid@example.com", "password": "password1", "display_name": "Rid"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "rid-doc", "text": "trace me"},
    ).json()
    trace = "proc-job-trace-99"
    accepted = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers={**headers, "X-Request-ID": trace},
        json={
            "version_id": source["version_id"],
            "wait": False,
            "chunk": False,
            "extract": False,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{job_id}",
        headers=headers,
    ).json()
    assert detail["job"]["options"]["request_id"] == trace


def test_active_job_conflict_and_retry_attempt(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "retry@example.com", "password": "password1", "display_name": "Retry"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "retry-doc", "text": "plain text"},
    ).json()

    options = {
        "chunk": False,
        "chunk_size": 1800,
        "chunk_overlap": 250,
        "extract": False,
        "ner_method": "llm",
        "relation_method": "llm",
        "extract_relations": True,
        "extract_triplets": False,
    }
    first, _ = app.state.knowledge_store.create_processing_job(
        workspace_id,
        version_id=source["version_id"],
        options=options,
    )
    conflict = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={"version_id": source["version_id"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "processing_active"

    app.state.knowledge_store.fail_job(workspace_id, first["id"], "forced", "forced")
    app.state.knowledge_store.fail_version(workspace_id, source["version_id"], "forced", "forced")
    retried = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs/{first['id']}/retry",
        headers=headers,
        json={"wait": True},
    )
    assert retried.status_code == 200
    jobs = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers).json()["jobs"]
    assert jobs[0]["attempt"] == 2
    assert jobs[0]["status"] == "succeeded"


def test_processing_job_idempotency_key_replay(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "idem@example.com", "password": "password1", "display_name": "Idem"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "idem-doc", "text": "repeat me"},
    ).json()

    payload = {
        "version_id": source["version_id"],
        "wait": True,
        "chunk": False,
        "extract": False,
        "ner_method": "llm",
        "relation_method": "llm",
        "idempotency_key": "process-once",
    }
    first = client.post(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers, json=payload)
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]

    second = client.post(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers, json=payload)
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert second.json()["job_id"] == first_job_id

    jobs = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers).json()["jobs"]
    assert len(jobs) == 1


def test_markdown_defaults_to_structural_chunking(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "md@example.com", "password": "password1", "display_name": "Md"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={"file": ("readme.md", b"# Title\n\nBody\n", "text/markdown")},
    )
    assert uploaded.status_code == 200
    version_id = uploaded.json()["version_id"]

    omitted = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={"version_id": version_id, "chunk": False, "extract": False},
    )
    assert omitted.status_code in {200, 202}
    jobs = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers).json()["jobs"]
    assert jobs[0]["options"]["chunk_method"] == "structural"


def test_rejects_unknown_chunk_method(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "chunk@example.com", "password": "password1", "display_name": "Chunk"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "chunk-method", "text": "Hello world."},
    ).json()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "chunk_method": "llm",
            "wait": False,
            "extract": False,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_chunk_method"
