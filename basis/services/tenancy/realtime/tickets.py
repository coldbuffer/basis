"""One-time WebSocket tickets (hashed at rest)."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass

from basis.services.errors import AdminError

_TICKET_TTL_SECONDS = 60


@dataclass
class _TicketRecord:
    workspace_id: str
    user_id: str
    expires_at: float
    used: bool = False


class RealtimeTicketStore:
    def __init__(self, *, ttl_seconds: int = _TICKET_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._by_digest: dict[str, _TicketRecord] = {}

    def issue(self, workspace_id: str, user_id: str) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = time.time() + self._ttl
        with self._lock:
            self._by_digest[digest] = _TicketRecord(
                workspace_id=workspace_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        return token, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires_at))

    def consume(self, workspace_id: str, token: str) -> str:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            record = self._by_digest.get(digest)
            if record is None:
                raise AdminError(401, "invalid_ticket", "票据无效")
            if record.used:
                raise AdminError(401, "ticket_used", "票据已使用")
            if record.workspace_id != workspace_id:
                raise AdminError(403, "wrong_workspace", "票据与工作区不匹配")
            if time.time() > record.expires_at:
                raise AdminError(401, "ticket_expired", "票据已过期")
            record.used = True
            return record.user_id
