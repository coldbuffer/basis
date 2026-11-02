"""Document version append and external_key reuse."""

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_same_doc_id_appends_version_and_supersedes_ready(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ver@example.com", "password": "password1", "display_name": "Ver"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "policy", "text": "Version one content."},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["version_no"] == 1
    assert body["new_document"] is True
    document_id = body["document_id"]

    processed = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={"version_id": body["version_id"], "wait": True, "chunk": False, "extract": False},
    )
    assert processed.status_code == 200
    assert processed.json()["ledger_status"] == "ready"

    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "policy", "text": "Version two content."},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["document_id"] == document_id
    assert second_body["version_no"] == 2
    assert second_body["new_document"] is False
    assert second_body["new_version"] is True
    assert second_body["status"] == "uploaded"

    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    policy_rows = [d for d in docs if d.get("doc_id") == "policy"]
    assert len(policy_rows) == 1
    assert policy_rows[0]["version_no"] == 2
    assert policy_rows[0]["created_at"]
    assert policy_rows[0]["updated_at"] >= policy_rows[0]["created_at"]


def test_unchanged_content_skips_new_version(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "same@example.com", "password": "password1", "display_name": "Same"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    text = "Identical bytes."
    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "stable", "text": text},
    ).json()
    again = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "stable", "text": text},
    )
    assert again.status_code == 200
    payload = again.json()
    assert payload["unchanged"] is True
    assert payload["new_version"] is False
    assert payload["version_id"] == first["version_id"]
    assert payload["version_no"] == 1


def test_explicit_version_upload_route(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "up@example.com", "password": "password1", "display_name": "Up"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "manual", "text": "first"},
    ).json()

    updated = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{created['document_id']}/versions",
        headers=headers,
        json={"text": "second"},
    )
    assert updated.status_code == 200
    assert updated.json()["version_no"] == 2
    assert updated.json()["new_version"] is True


def test_filename_only_for_uploaded_files(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "name@example.com", "password": "password1", "display_name": "Name"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    pasted = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "note", "text": "pasted body"},
    )
    assert pasted.status_code == 200

    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={"file": ("规范说明.md", BytesIO(b"# hello"), "text/markdown")},
    )
    assert uploaded.status_code == 200

    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    by_id = {row["doc_id"]: row for row in docs}
    assert by_id["note"]["filename"] is None
    uploaded_row = next(row for row in docs if row.get("filename") == "规范说明.md")
    assert uploaded_row["doc_id"] == "upload"
    assert uploaded_row["doc_id"] != uploaded_row["filename"]


def test_document_list_is_newest_upload_first(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "order@example.com", "password": "password1", "display_name": "Order"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "older", "text": "first"},
    )
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "newer", "text": "second"},
    )
    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    ids = [row["doc_id"] for row in docs]
    assert ids.index("newer") < ids.index("older")
    created = [row["created_at"] for row in docs]
    assert created == sorted(created, reverse=True)


def test_ingest_document_from_url(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "url@example.com", "password": "password1", "display_name": "Url"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    with patch(
        "basis.services.knowledge.services.ingest_source_service.fetch_http_poll_text",
        return_value="Fetched from remote URL.",
    ) as mock_fetch:
        resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/documents",
            headers=headers,
            json={"doc_id": "remote-doc", "url": "https://example.com/notes.txt"},
        )
    assert resp.status_code == 200
    mock_fetch.assert_called_once_with("https://example.com/notes.txt")
    body = resp.json()
    assert body["doc_id"] == "remote-doc"
    assert body["version_no"] == 1
    assert body["status"] == "uploaded"
