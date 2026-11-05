"""Vertical-slice release gate checks (implementation-backlog §9)."""

from __future__ import annotations

import io
import shutil
import sqlite3
import tarfile

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def _settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, ingest_inline=True)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict[str, str]:
    body = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "U"},
    ).json()
    return _auth(body["token"])


def _minimal_docx_bytes() -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Alice knows Bob.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _viewer_headers(
    client: TestClient,
    owner_headers: dict[str, str],
    workspace_id: str,
    *,
    email: str = "viewer-gate@example.com",
) -> dict[str, str]:
    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "V"},
    ).json()
    users = client.get("/api/v1/users", headers=owner_headers).json()["users"]
    viewer_user = next(u for u in users if u["email"] == email)
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{viewer_user['id']}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    return _auth(viewer["token"])


def test_docx_upload_creates_document_chunks_and_statements(tmp_path) -> None:
    """§9.1 — DOCX upload produces canonical document, version, chunks, and statements."""
    docx_bytes = _minimal_docx_bytes()
    client = TestClient(create_app(_settings(tmp_path)))
    headers = _register(client, "docx@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    upload = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={
            "file": (
                "gate.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"doc_id": "gate-docx", "extract": "true", "wait": "true"},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["doc_id"] == "gate-docx"
    assert body["chunk_count"] >= 1
    assert body["ledger_statement_count"] >= 1
    assert body["ledger_statements_written"] >= 1

    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    assert any(d.get("doc_id") == "gate-docx" for d in docs)

    chunks = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/documents/gate-docx/chunks",
        headers=headers,
    ).json()["chunks"]
    assert len(chunks) >= 1
    chunk_id = chunks[0]["id"]

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/chunks/{chunk_id}", headers=headers).json()
    assert "Alice" in detail["chunk"]["text"]
    statements = detail["statements"]
    assert len(statements) >= 1
    assert statements[0]["statement_id"]
    assert statements[0].get("quote")


def test_extracted_graph_edges_carry_statement_and_evidence_refs(tmp_path) -> None:
    """§9.2 — open-layer extracted relations expose stable statement/evidence ids on the graph."""
    docx_bytes = _minimal_docx_bytes()
    client = TestClient(create_app(_settings(tmp_path)))
    headers = _register(client, "refs@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={
            "file": (
                "gate.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"doc_id": "gate-docx", "extract": "true", "wait": "true"},
    )

    snap = client.get(f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers).json()
    open_edges = [
        e
        for e in snap["edges"]
        if e.get("projection_layer") == "open" and e.get("statement_id")
    ]
    assert open_edges, "expected at least one open projection edge with statement_id"
    for edge in open_edges:
        assert edge["statement_id"]
        assert edge.get("evidence_id")


def test_graph_page_api_is_workspace_scoped_not_global(tmp_path) -> None:
    """§9.6 — graph HTTP surface is per-workspace (Basis graph page uses injected workspace apiRoot)."""
    client = TestClient(create_app(_settings(tmp_path)))
    headers = _register(client, "scope@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    scoped = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=headers)
    assert scoped.status_code == 200
    assert "node_count" in scoped.json()

    global_graph = client.get("/api/graph/stats", headers=headers)
    assert global_graph.status_code in (404, 405, 410)


def test_viewer_cannot_upload_or_create_documents(tmp_path) -> None:
    """§9.4 — viewers may browse but cannot mutate workspace content."""
    client = TestClient(create_app(_settings(tmp_path)))
    owner_headers = _register(client, "owner-gate@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=owner_headers).json()["workspaces"][0]["id"]
    viewer_headers = _viewer_headers(client, owner_headers, workspace_id)

    browse = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=viewer_headers)
    assert browse.status_code == 200

    denied_json = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=viewer_headers,
        json={"doc_id": "viewer-doc", "text": "nope", "extract": False},
    )
    assert denied_json.status_code == 403

    denied_upload = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=viewer_headers,
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"extract": "false"},
    )
    assert denied_upload.status_code == 403

    denied_rebuild = client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=viewer_headers)
    assert denied_rebuild.status_code == 403


def test_viewer_can_read_graph_and_cannot_start_processing(tmp_path) -> None:
    """§9.4 — viewers browse graph APIs; processing start requires editor."""
    client = TestClient(create_app(_settings(tmp_path)))
    owner_headers = _register(client, "owner-vbrowse@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=owner_headers).json()["workspaces"][0]["id"]
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=owner_headers,
        json={"doc_id": "gate-doc", "text": "Alice knows Bob.", "extract": False},
    )
    assert uploaded.status_code == 200
    version_id = uploaded.json()["version_id"]
    client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=owner_headers)

    viewer_headers = _viewer_headers(
        client,
        owner_headers,
        workspace_id,
        email="viewer-browse@example.com",
    )
    assert client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=viewer_headers).status_code == 200
    assert client.get(f"/api/v1/workspaces/{workspace_id}/graph/nodes", headers=viewer_headers).status_code == 200
    search = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/search",
        headers=viewer_headers,
        json={"query": "Alice", "limit": 10},
    )
    assert search.status_code == 200

    denied_job = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=viewer_headers,
        json={"version_id": version_id, "wait": False, "extract": False, "chunk": False},
    )
    assert denied_job.status_code == 403


def test_viewer_cannot_apply_reasoning_to_graph(tmp_path) -> None:
    """§9.4 — viewers may run dry-run reasoning but not mutate the graph."""
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(_settings(tmp_path)))
    owner_headers = _register(client, "owner-reason@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=owner_headers).json()["workspaces"][0]["id"]
    viewer_headers = _viewer_headers(client, owner_headers, workspace_id)

    dry_run = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=viewer_headers,
        json={
            "facts": ["inhibits(A, B)"],
            "rules": ["IF inhibits(A, B) THEN related(A, B)"],
            "mode": "forward",
            "apply_to_graph": False,
        },
    )
    assert dry_run.status_code == 200

    denied_apply = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=viewer_headers,
        json={
            "facts": ["inhibits(A, B)"],
            "rules": ["IF inhibits(A, B) THEN related(A, B)"],
            "mode": "forward",
            "apply_to_graph": True,
        },
    )
    assert denied_apply.status_code == 403


def test_ledger_and_projection_survive_app_restart(tmp_path) -> None:
    """§9.3 / §9.8 — canonical data on disk survives a new API process."""
    settings = _settings(tmp_path)
    client = TestClient(create_app(settings))
    headers = _register(client, "restart@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "persist-doc", "text": "persist me", "extract": False},
    )
    before = client.get(f"/api/v1/workspaces/{workspace_id}/graph/projection", headers=headers).json()
    rev_before = before["revision"]

    client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers)

    client.close()
    client2 = TestClient(create_app(settings))
    logged_in = client2.post(
        "/api/v1/auth/login",
        json={"email": "restart@example.com", "password": "password1"},
    ).json()
    headers2 = _auth(logged_in["token"])
    workspace_id2 = client2.get("/api/v1/workspaces", headers=headers2).json()["workspaces"][0]["id"]
    assert workspace_id2 == workspace_id

    after = client2.get(f"/api/v1/workspaces/{workspace_id}/graph/projection", headers=headers2).json()
    assert after["revision"] >= rev_before

    snap = client2.get(f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers2)
    assert snap.status_code == 200
    node_ids = {n["id"] for n in snap.json()["nodes"]}
    assert "persist-doc" in node_ids


def test_dual_workspace_graph_snapshot_isolation(tmp_path) -> None:
    """§9.5 — graph projection nodes do not leak across KBs (HTTP)."""
    client = TestClient(create_app(_settings(tmp_path)))
    headers = _register(client, "dual@example.com")
    workspace_a = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    workspace_b = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "B", "visibility": "restricted"},
    ).json()["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_a}/documents",
        headers=headers,
        json={"doc_id": "only-on-a", "text": "A", "extract": False},
    )
    client.post(
        f"/api/v1/workspaces/{workspace_b}/documents",
        headers=headers,
        json={"doc_id": "only-on-b", "text": "B", "extract": False},
    )

    snap_a = client.get(f"/api/v1/workspaces/{workspace_a}/graph/snapshot", headers=headers).json()
    snap_b = client.get(f"/api/v1/workspaces/{workspace_b}/graph/snapshot", headers=headers).json()
    ids_a = {n["id"] for n in snap_a["nodes"]}
    ids_b = {n["id"] for n in snap_b["nodes"]}

    assert "only-on-a" in ids_a
    assert "only-on-a" not in ids_b
    assert "only-on-b" in ids_b
    assert "only-on-b" not in ids_a


def test_rebuild_is_idempotent_for_empty_ledger_change(tmp_path) -> None:
    """§9.3 — repeated rebuild without ledger changes bumps revision monotonically."""
    client = TestClient(create_app(_settings(tmp_path)))
    headers = _register(client, "rebuild@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "rb-doc", "text": "x", "extract": False},
    )
    first = client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers).json()
    second = client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers).json()
    assert second["projection_revision"] >= first["projection_revision"]

    snap = client.get(f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers).json()
    assert "rb-doc" in {n["id"] for n in snap["nodes"]}


def _checkpoint_sqlite(data_dir) -> None:
    db = data_dir / "basis.db"
    if not db.is_file():
        return
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def _tar_data_dir(data_dir, archive) -> None:
    _checkpoint_sqlite(data_dir)
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(data_dir.iterdir()):
            if path.name == "basis.db" or path.name.startswith("basis.db-") or path.name in {
                "blobs",
                "graphs",
            }:
                tar.add(path, arcname=path.name)


def test_backup_tar_roundtrip_preserves_ledger(tmp_path) -> None:
    """§9.8 / X-03 — tar backup/restore keeps ledger; projection rebuilds without graph files."""
    data_dir = tmp_path / "live"
    data_dir.mkdir()
    settings = _settings(data_dir)
    client = TestClient(create_app(settings))
    headers = _register(client, "backup@example.com")
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "backup-doc", "text": "keep", "extract": False},
    )
    client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers)
    client.close()

    archive = tmp_path / "basis-backup.tar.gz"
    _tar_data_dir(data_dir, archive)

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(restore_dir, filter="data")

    graphs_dir = restore_dir / "graphs"
    if graphs_dir.is_dir():
        shutil.rmtree(graphs_dir)

    client2 = TestClient(create_app(_settings(restore_dir)))
    owner = client2.post(
        "/api/v1/auth/login",
        json={"email": "backup@example.com", "password": "password1"},
    ).json()
    headers2 = _auth(owner["token"])

    docs = client2.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers2).json()["documents"]
    assert any(d.get("doc_id") == "backup-doc" for d in docs)

    rebuild = client2.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers2)
    assert rebuild.status_code == 200
    snap = client2.get(f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers2).json()
    assert "backup-doc" in {n["id"] for n in snap["nodes"]}
