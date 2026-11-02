"""User accounts."""

from __future__ import annotations

from typing import Any

from basis.services.tenancy.admin.admin_types import User, utc_now_iso, user_from_row
from basis.services.tenancy.admin.passwords import hash_password


def fetch_user(conn: Any, user_id: str) -> Any | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def active_by_email(conn: Any, email: str) -> Any | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ? AND deactivated_at IS NULL", (email,)
    ).fetchone()


def user_count(conn: Any) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def active_admin_count(conn: Any) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1 AND deactivated_at IS NULL"
    ).fetchone()["n"]


def list_users(conn: Any, *, deactivated: bool) -> list[Any]:
    clause = "deactivated_at IS NOT NULL" if deactivated else "deactivated_at IS NULL"
    return conn.execute(f"SELECT * FROM users WHERE {clause} ORDER BY created_at").fetchall()


def insert_user(
    conn: Any,
    *,
    email: str,
    password: str,
    display_name: str,
    is_admin: bool,
    user_id: str,
) -> User:
    created_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO users(id, email, display_name, password_hash, is_admin, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, email, display_name, hash_password(password), int(is_admin), created_at),
    )
    return User(user_id, email, display_name, is_admin, None, created_at)


def insert_user_federated(
    conn: Any,
    *,
    user_id: str,
    email: str,
    display_name: str,
    password_hash: str,
) -> User:
    created_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO users(id, email, display_name, password_hash, is_admin, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (user_id, email, display_name, password_hash, created_at),
    )
    return User(user_id, email, display_name, False, None, created_at)


def deactivate_user(conn: Any, target_id: str, deactivated_at: str) -> None:
    conn.execute("UPDATE users SET deactivated_at = ? WHERE id = ?", (deactivated_at, target_id))


def reactivate_user(conn: Any, target_id: str) -> None:
    conn.execute("UPDATE users SET deactivated_at = NULL WHERE id = ?", (target_id,))


def user_by_session_token(conn: Any, token_hash: str) -> Any | None:
    return conn.execute(
        """
        SELECT u.* FROM tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = ? AND u.deactivated_at IS NULL
        """,
        (token_hash,),
    ).fetchone()


def delete_session_tokens_for_user(conn: Any, user_id: str) -> None:
    conn.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,))


def issue_session_token(conn: Any, token_hash: str, user_id: str) -> None:
    conn.execute(
        "INSERT INTO tokens(token_hash, user_id, created_at) VALUES (?, ?, ?)",
        (token_hash, user_id, utc_now_iso()),
    )


def delete_session_token(conn: Any, token_hash: str) -> None:
    conn.execute("DELETE FROM tokens WHERE token_hash = ?", (token_hash,))
