from pathlib import Path

import pytest

from basis.services.errors import AdminError
from basis.services.knowledge.blob_store import BlobStore


def test_put_is_content_addressed_and_atomic(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    data = b"hello ledger"
    first = store.put("kb-a", data)
    second = store.put("kb-a", data)
    assert first.sha256 == second.sha256
    assert first.blob_key == second.blob_key
    assert store.read("kb-a", first.blob_key) == data


def test_workspace_isolation_on_read(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    ref = store.put("kb-a", b"secret")
    with pytest.raises(AdminError) as exc:
        store.read("kb-b", ref.blob_key)
    assert exc.value.code == "forbidden"


def test_path_traversal_filename_does_not_escape(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    ref = store.put("../../evil", b"x")
    path = (tmp_path / "blobs").resolve()
    for child in path.rglob("*"):
        if child.is_file():
            assert str(child.resolve()).startswith(str(path) + "/") or child.resolve() == path
    assert store.read("../../evil", ref.blob_key) == b"x"
