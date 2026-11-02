"""Platform-wide BOCP provider allowlist (stored in ``settings``)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from basis.services.connector.vault.allowlist import (
    PLATFORM_CONNECTOR_ALLOWLIST_KEY,
    normalize_allowed_providers,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformConnectorPolicy:
    """Read/write platform connector allowlist on a DB-API connection."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def get_allowed_providers(self) -> list[str] | str:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (PLATFORM_CONNECTOR_ALLOWLIST_KEY,),
        ).fetchone()
        if not row or not row[0]:
            return "*"
        try:
            parsed = json.loads(row[0])
        except json.JSONDecodeError:
            return "*"
        return normalize_allowed_providers(parsed)

    def upsert_allowed_providers(
        self,
        allowed_providers: list[str] | str,
        *,
        commit: bool = True,
    ) -> tuple[list[str] | str, str]:
        normalized = normalize_allowed_providers(allowed_providers)
        now = _now_iso()
        payload = json.dumps(normalized, ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (PLATFORM_CONNECTOR_ALLOWLIST_KEY, payload),
        )
        if commit:
            self._conn.commit()
        return normalized, now


def get_platform_allowed_providers(conn: Any) -> list[str] | str:
    return PlatformConnectorPolicy(conn).get_allowed_providers()


def upsert_platform_allowed_providers(
    conn: Any,
    allowed_providers: list[str] | str,
) -> tuple[list[str] | str, str]:
    return PlatformConnectorPolicy(conn).upsert_allowed_providers(allowed_providers)
