from pathlib import Path

import pytest

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def _workspace_id(tmp_path: Path, *, email: str = "u@example.com", name: str = "Test KB") -> str:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register(email, "password1", "U")
    workspace = admin.create_workspace(user, name, None, "restricted")
    admin.close()
    return workspace.id


def test_store_upload_and_read_roundtrip(tmp_path: Path) -> None:
    workspace_id = _workspace_id(tmp_path)
    blobs = BlobStore(tmp_path)
    store = KnowledgeStore(tmp_path / "basis.db", blobs)
    doc_id, version_id, job_id, blob = store.store_upload_bytes(
        workspace_id,
        title="note.txt",
        mime_type="text/plain",
        data=b"alpha",
        created_by=None,
    )
    assert doc_id and version_id and job_id
    assert blob.byte_size == 5
    assert store.read_version_bytes(workspace_id, version_id) == b"alpha"
    row = store.get_version(workspace_id, version_id)
    assert row.status == "queued"
    store.close()


def test_same_bytes_two_versions_two_documents(tmp_path: Path) -> None:
    workspace_id = _workspace_id(tmp_path)
    blobs = BlobStore(tmp_path)
    store = KnowledgeStore(tmp_path / "basis.db", blobs)
    d1, v1, _, _ = store.store_upload_bytes(
        workspace_id, title="a", mime_type="text/plain", data=b"same", created_by=None
    )
    d2, v2, _, _ = store.store_upload_bytes(
        workspace_id, title="b", mime_type="text/plain", data=b"same", created_by=None
    )
    assert d1 != d2
    assert v1 != v2
    store.close()


def test_open_statement_validation_and_workspace_guard(tmp_path: Path) -> None:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("stmt@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB A", None, "restricted").id
    other_workspace = admin.create_workspace(user, "KB B", None, "restricted").id
    admin.close()
    blobs = BlobStore(tmp_path)
    store = KnowledgeStore(tmp_path / "basis.db", blobs)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id, title="doc", mime_type="text/plain", data=b"x", created_by=None
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob.")
    e1 = store.create_entity(workspace_id, canonical_label="Alice")
    e2 = store.create_entity(workspace_id, canonical_label="Bob")
    e3 = store.create_entity(workspace_id, canonical_label="Alice")
    assert store.count_entities_named(workspace_id, "Alice") == 2

    quote = "knows Bob"
    start = "Alice knows Bob.".index(quote)
    end = start + len(quote)
    sid = store.add_open_statement(
        workspace_id,
        subject_id=e1,
        surface_phrase="knows",
        object_entity_id=e2,
        object_value=None,
        status="confirmed",
        proposed_by="pattern",
        chunk_id=chunk_id,
        quote=quote,
        quote_start=start,
        quote_end=end,
    )
    assert sid

    with pytest.raises(AdminError) as bad:
        store.add_open_statement(
            workspace_id,
            subject_id=e1,
            surface_phrase="x",
            object_entity_id=e2,
            object_value="also",
            status="confirmed",
            proposed_by="pattern",
            chunk_id=chunk_id,
            quote="x",
        )
    assert bad.value.code == "bad_statement"

    with pytest.raises(AdminError) as cross:
        store.add_open_statement(
            other_workspace,
            subject_id=e1,
            surface_phrase="knows",
            object_entity_id=e2,
            object_value=None,
            status="confirmed",
            proposed_by="pattern",
            chunk_id=chunk_id,
            quote=quote,
            quote_start=start,
            quote_end=end,
        )
    assert cross.value.code == "forbidden"
    store.close()
