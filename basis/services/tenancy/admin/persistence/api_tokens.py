"""Per-user API tokens."""

from __future__ import annotations

import json
from typing import Any

from basis.services.tenancy.admin.admin_types import utc_now_iso


def fetch_api_token(conn: Any, token_id: str) -> Any | None:
    return conn.execute("SELECT * FROM api_tokens WHERE id = ?", (token_id,)).fetchone()


def list_api_tokens_for_user(conn: Any, user_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT * FROM api_tokens
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()


def insert_api_token(
    conn: Any,
    *,
    token_id: str,
    token_hash: str,
    token_secret: str,
    user_id: str,
    name: str,
    scope: str,
    workspace_ids_json: str,
    allowed_operations_json: str | None,
    created_at: str,
    expires_at: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO api_tokens(
            id, token_hash, token_secret, user_id, name, scope, workspace_ids_json,
            allowed_operations_json, created_at, expires_at, last_used_at, revoked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            token_id,
            token_hash,
            token_secret,
            user_id,
            name,
            scope,
            workspace_ids_json,
            allowed_operations_json,
            created_at,
            expires_at,
        ),
    )


def revoke_api_token(conn: Any, token_id: str, revoked_at: str) -> None:
    conn.execute(
        "UPDATE api_tokens SET revoked_at = ?, token_secret = NULL WHERE id = ?",
        (revoked_at, token_id),
    )


def delete_api_token(conn: Any, token_id: str) -> None:
    conn.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))


def resolve_api_token_row(conn: Any, token_hash: str) -> Any | None:
    return conn.execute(
        """
        SELECT t.*, u.id AS uid, u.email, u.display_name, u.is_admin,
               u.deactivated_at, u.created_at AS user_created_at
        FROM api_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = ? AND u.deactivated_at IS NULL
        """,
        (token_hash,),
    ).fetchone()


def touch_api_token_last_used(conn: Any, token_id: str) -> None:
    conn.execute(
        "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
        (utc_now_iso(), token_id),
    )
