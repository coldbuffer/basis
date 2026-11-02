from pathlib import Path

from basis.services.tenancy.admin.store import AdminStore
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.services.knowledge.pipeline.chunk_meta import prepare_chunks
from basis.services.knowledge.pipeline.document import TextIngestOptions


def test_prepare_chunks_records_heading_offsets_and_language() -> None:
    import json

    text = "# Intro\n\n" + ("alpha " * 80) + "\n\n# Methods\n\n" + ("汉字内容 " * 80)
    rows = prepare_chunks(
        text,
        TextIngestOptions(chunk=True, chunk_size=300, chunk_overlap=20),
    )
    assert len(rows) > 1
    assert rows[0]["heading"] == "Intro"
    assert rows[0]["language"] == "en"
    assert rows[0]["origin"] == "stated"
    assert rows[0]["char_start"] == 0
    assert text[rows[0]["char_start"] : rows[0]["char_end"]] == rows[0]["text"]
    assert rows[0]["token_count"] > 0
    assert json.loads(rows[0]["anchor_json"])["heading"] == "Intro"
    later = next(row for row in rows if row["heading"] == "Methods" and row["language"] == "zh")
    assert text[later["char_start"] : later["char_end"]] == later["text"]


def test_create_chunks_persists_metadata(tmp_path: Path) -> None:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("chunk-meta@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="note.md",
        mime_type="text/markdown",
        data=b"# Intro\n\nHello",
        created_by=None,
    )
    payloads = prepare_chunks("# Intro\n\nHello", TextIngestOptions(chunk=True))
    store.create_chunks(workspace_id, version_id, payloads)
    listed = store.list_chunks_for_version(workspace_id, version_id)
    assert listed[0]["heading"] == "Intro"
    assert listed[0]["char_start"] == 0
    assert listed[0]["char_end"] == len("# Intro\n\nHello")
    assert listed[0]["language"] == "en"
    assert listed[0]["origin"] == "stated"
    assert listed[0]["token_count"] > 0
    assert listed[0]["anchor"]["heading"] == "Intro"
    detail = store.get_chunk(workspace_id, listed[0]["id"])
    assert detail is not None
    assert detail["heading"] == "Intro"
    assert detail["token_count"] == listed[0]["token_count"]
    store.close()


def test_prepare_chunks_paragraph_method() -> None:
    text = "First block line.\n\nSecond block line.\n\nThird block line."
    rows = prepare_chunks(
        text,
        TextIngestOptions(chunk=True, chunk_method="paragraph", chunk_size=40, chunk_overlap=0),
    )
    assert len(rows) >= 2
    assert all(row["text"].strip() for row in rows)
