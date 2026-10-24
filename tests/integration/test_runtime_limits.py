"""Runtime request limits from Settings (X-04)."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore


def test_settings_override_graph_snapshot_cap(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, graph_page_max_nodes=8, graph_page_max_edges=12)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "cap@example.com", "password": "password1", "display_name": "Cap"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    res = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/snapshot?limit_nodes=999&limit_edges=999",
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["nodes"]) <= 8
    assert len(body["edges"]) <= 12


def test_settings_override_chunk_search_cap(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, chunk_search_max_limit=2)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "search@example.com", "password": "password1", "display_name": "S"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="many.txt",
        mime_type="text/plain",
        data=b"token",
        created_by=None,
        external_key="many",
    )
    for ordinal in range(5):
        store.create_chunk(workspace_id, version_id, ordinal=ordinal, text=f"token chunk {ordinal}")
    store.set_version_status(workspace_id, version_id, "ready")
    store.close()

    res = client.get(f"/api/v1/workspaces/{workspace_id}/search?q=token&limit=50", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["chunks"]) <= 2


def test_document_upload_rejected_over_byte_cap(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, upload_max_bytes=64)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "up@example.com", "password": "password1", "display_name": "Up"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    over = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={"file": ("big.bin", b"x" * 128, "application/octet-stream")},
    )
    assert over.status_code == 413
    detail = over.json()["detail"]
    assert detail["code"] == "upload_too_large"

    text_over = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "big-text", "text": "y" * 128},
    )
    assert text_over.status_code == 413
    assert text_over.json()["detail"]["code"] == "upload_too_large"


def test_processing_fails_when_extracted_text_exceeds_cap(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        ingest_max_extract_chars=32,
        ingest_inline=True,
    )
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ext@example.com", "password": "password1", "display_name": "Ext"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "long-doc", "text": "word " * 20},
    ).json()

    failed = client.post(
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
    assert failed.status_code == 413
    assert failed.json()["detail"]["code"] == "extract_text_too_large"
    job = client.get(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
    ).json()["jobs"][0]
    assert job["status"] == "failed"
    assert job["error_code"] == "extract_text_too_large"


def test_processing_fails_when_chunk_count_exceeds_cap(tmp_path: Path, monkeypatch) -> None:
    from basis.domain.knowledge.pipeline import version_ingest as vi

    def _many_chunks(full_text: str, options) -> list[str]:
        return [f"part-{i}" for i in range(5)]

    monkeypatch.setattr(vi, "prepare_chunks", _many_chunks)

    settings = Settings(
        data_dir=tmp_path,
        ingest_max_chunks=3,
        ingest_inline=True,
    )
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "chk@example.com", "password": "password1", "display_name": "Chk"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "chunky", "text": "hello world"},
    ).json()

    failed = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "wait": True,
            "chunk": True,
            "chunk_size": 200,
            "chunk_overlap": 0,
            "extract": False,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert failed.status_code == 413
    assert failed.json()["detail"]["code"] == "too_many_chunks"


def test_processing_fails_when_extraction_times_out(tmp_path: Path, monkeypatch) -> None:
    from basis.domain.knowledge.pipeline import document
    from basis.domain.knowledge.pipeline.extract_timeout import ExtractionTimeoutError

    def _always_timeout(_fn, timeout_seconds: float):
        raise ExtractionTimeoutError(timeout_seconds)

    monkeypatch.setattr(document, "run_sync_with_timeout", _always_timeout)

    settings = Settings(
        data_dir=tmp_path,
        ingest_extract_timeout_seconds=30,
        ingest_inline=True,
    )
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "to@example.com", "password": "password1", "display_name": "To"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    source = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "slow-ext", "text": "Alice knows Bob."},
    ).json()

    failed = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": source["version_id"],
            "wait": True,
            "chunk": False,
            "extract": True,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert failed.status_code == 504
    assert failed.json()["detail"]["code"] == "extract_timeout"


def test_async_ingest_fails_with_ingest_overloaded_when_pending_full(
    tmp_path: Path, monkeypatch
) -> None:
    from basis.domain.knowledge.pipeline import version_ingest as vi

    original = vi.run_version_ingest

    def slow_ingest(*args, **kwargs):
        time.sleep(2)
        return original(*args, **kwargs)

    monkeypatch.setattr(vi, "run_version_ingest", slow_ingest)

    settings = Settings(
        data_dir=tmp_path,
        ingest_max_pending=1,
        ingest_max_inflight=1,
    )
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "q@example.com", "password": "password1", "display_name": "Q"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    a = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "qa", "text": "one"},
    ).json()
    b = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "qb", "text": "two"},
    ).json()
    payload = {
        "wait": False,
        "chunk": False,
        "extract": False,
        "ner_method": "llm",
        "relation_method": "llm",
    }
    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={**payload, "version_id": a["version_id"]},
    )
    assert first.status_code == 202
    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={**payload, "version_id": b["version_id"]},
    )
    assert second.status_code == 202
    jobs = client.get(f"/api/v1/workspaces/{workspace_id}/processing/jobs", headers=headers).json()["jobs"]
    overloaded = [j for j in jobs if j.get("error_code") == "ingest_overloaded"]
    assert len(overloaded) == 1


def test_run_sync_with_timeout_returns_without_waiting_on_worker() -> None:
    import pytest

    from basis.domain.knowledge.pipeline.extract_timeout import ExtractionTimeoutError, run_sync_with_timeout

    start = time.monotonic()
    with pytest.raises(ExtractionTimeoutError):
        run_sync_with_timeout(lambda: time.sleep(5), 0.15)
    assert time.monotonic() - start < 1.5
