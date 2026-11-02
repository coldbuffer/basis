from io import BytesIO
from pathlib import Path
import time
from unittest.mock import patch

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.graph.projection.session import GraphSession
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.services.knowledge.pipeline.document import TextIngestOptions
from basis.services.knowledge.pipeline.version_ingest import run_version_ingest


def _workspace_id(tmp_path: Path) -> str:
    from basis.services.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("ingest@example.com", "password1", "U")
    workspace = admin.create_workspace(user, "KB", None, "restricted")
    admin.close()
    return workspace.id


def test_run_version_ingest_chunks_and_marks_ready(tmp_path: Path) -> None:
    workspace_id = _workspace_id(tmp_path)
    blobs = BlobStore(tmp_path)
    knowledge = KnowledgeStore(tmp_path / "basis.db", blobs)
    text = b"Line one.\nLine two about contracts."
    _, version_id, job_id, _ = knowledge.store_upload_bytes(
        workspace_id,
        title="clause.txt",
        mime_type="text/plain",
        data=text,
        created_by=None,
        external_key="clause",
    )
    graph = GraphSession()
    result = run_version_ingest(
        knowledge,
        graph,
        workspace_id,
        version_id,
        job_id,
        filename="clause.txt",
        graph_doc_id="clause",
        options=TextIngestOptions(extract=False, chunk=True, chunk_size=20, chunk_overlap=0),
    )
    assert result["ledger_status"] == "ready"
    assert result["chunk_count"] >= 1
    assert knowledge.get_version(workspace_id, version_id).status == "ready"
    assert knowledge.get_job(workspace_id, job_id).status == "succeeded"
    assert graph.stats()["node_count"] >= 1
    knowledge.close()


def test_ingest_failure_before_rebuild_marks_projection_dirty(tmp_path: Path) -> None:
    workspace_id = _workspace_id(tmp_path)
    blobs = BlobStore(tmp_path)
    knowledge = KnowledgeStore(tmp_path / "basis.db", blobs)
    _, version_id, job_id, _ = knowledge.store_upload_bytes(
        workspace_id,
        title="dirty.txt",
        mime_type="text/plain",
        data=b"Alice knows Bob.",
        created_by=None,
        external_key="dirty-doc",
    )
    graph = GraphSession()
    knowledge.set_projection_status(workspace_id, "clean")

    with patch(
        "basis.services.knowledge.pipeline.version_ingest.apply_rebuild_to_session",
        side_effect=RuntimeError("rebuild unavailable"),
    ):
        with pytest.raises(RuntimeError, match="rebuild unavailable"):
            run_version_ingest(
                knowledge,
                graph,
                workspace_id,
                version_id,
                job_id,
                filename="dirty.txt",
                graph_doc_id="dirty-doc",
                options=TextIngestOptions(extract=False, chunk=True),
            )

    assert knowledge.get_version(workspace_id, version_id).status == "failed"
    assert knowledge.get_job(workspace_id, job_id).status == "failed"
    assert knowledge.get_projection_state(workspace_id)["status"] == "dirty"
    assert knowledge.get_projection_state(workspace_id)["last_error_code"] == "ingest_incomplete"
    knowledge.close()


def test_upload_api_async_accept_and_polls_succeeded(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "async@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    files = {"file": ("async.txt", BytesIO(b"async ingest body"), "text/plain")}
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files=files,
        data={"extract": "false", "wait": "false"},
    )
    assert uploaded.status_code == 202
    body = uploaded.json()
    assert body.get("accepted") is True
    assert body.get("job_id") and body.get("version_id")

    for _ in range(60):
        job = client.get(
            f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{body['job_id']}",
            headers=headers,
        )
        assert job.status_code == 200
        status = job.json()["job"]["status"]
        if status in {"succeeded", "failed"}:
            assert status == "succeeded"
            break
        time.sleep(0.1)
    else:
        raise AssertionError("job did not finish")


def test_upload_api_returns_job_and_polls_succeeded(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "up@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    files = {"file": ("demo.txt", BytesIO(b"payment terms and delivery"), "text/plain")}
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files=files,
        data={"extract": "false"},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body.get("job_id") and body.get("version_id") and body.get("document_id")
    assert body.get("ledger_status") == "ready"

    job = client.get(
        f"/api/v1/workspaces/{workspace_id}/ingest/jobs/{body['job_id']}",
        headers=headers,
    )
    assert job.status_code == 200
    assert job.json()["job"]["status"] == "succeeded"
    assert job.json()["version"]["status"] == "ready"
