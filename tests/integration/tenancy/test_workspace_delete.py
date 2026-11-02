"""Workspace hard delete purges ledger rows that block the workspaces FK."""

from pathlib import Path

from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.services.tenancy.admin.store import AdminStore


def test_delete_workspace_after_entities_exist(tmp_path: Path) -> None:
    db_path = tmp_path / "basis.db"
    admin = AdminStore(db_path)
    user, _ = admin.register("del@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "Delete me", None, "restricted").id

    knowledge = KnowledgeStore(db_path, BlobStore(tmp_path))
    knowledge.create_entity(workspace_id, canonical_label="Leftover")

    admin.delete_workspace(user, workspace_id)
    assert workspace_id not in admin.list_workspace_ids()
    admin.close()
