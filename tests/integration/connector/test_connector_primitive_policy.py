"""Workspace action_policy governance for BOCP primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from basis.services.connector import ConnectorAuthVault, ConnectorPolicy
def test_resolve_primitive_execution_mode_entities_map() -> None:
    pol = ConnectorPolicy(
        workspace_id="kb1",
        action_policy={
            "entities": {
                "github:issues.list": "disabled",
                "issues.create": "auto",
            },
            "default_entity_write_mode": "review",
        },
    )
    assert pol.resolve_primitive_execution_mode("github", "issues", "list") == "disabled"
    assert (
        pol.resolve_primitive_execution_mode(
            "github", "issues", "mutate", operation="create"
        )
        == "auto"
    )
    assert (
        pol.resolve_primitive_execution_mode(
            "github", "issues", "mutate", operation="update"
        )
        == "review"
    )


def test_primitive_disabled_blocks_invoke(tmp_path: Path) -> None:
    from basis.services.connector.primitive_invoke import execute_connector_primitive
    from basis.services.connector.runtime import ConnectorRuntime
    from basis.infra.db.sqlite_migrations import run_migrations
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / "basis.db"))
    run_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        INSERT INTO users (id, email, display_name, password_hash, is_admin, created_at)
        VALUES ('u1', 'u1@example.com', 'User 1', 'hash', 1, '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO workspaces (id, name, description, visibility, created_by, created_at)
        VALUES ('kb1', 'KB 1', '', 'private', 'u1', '2026-01-01T00:00:00Z')
        """
    )
    conn.commit()
    try:
        vault = ConnectorAuthVault(conn, vault_secret="secret")
        vault.upsert_policy(
            "kb1",
            allowed_providers=["postgres"],
            action_policy={"entities": {"table_records.list": "disabled"}},
        )
        vault.upsert_connection(
            "kb1",
            "postgres",
            auth_type="database_dsn",
            connection_config={"dsn": "sqlite:///:memory:"},
            credentials={},
        )
        runtime = ConnectorRuntime(conn, vault_secret="secret")
        with pytest.raises(PermissionError):
            execute_connector_primitive(
                runtime,
                "kb1",
                "postgres",
                action_id="table_records",
                primitive="list",
                external_table="x",
            )
    finally:
        conn.close()
