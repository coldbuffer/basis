"""Platform settings key/value store."""

from __future__ import annotations

from typing import Any


def get_setting(conn: Any, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def put_setting(conn: Any, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def delete_setting(conn: Any, key: str) -> None:
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
