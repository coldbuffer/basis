"""API token management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from basis.services.tenancy.admin.admin_types import (
    ApiTokenRecord,
    User,
    api_token_from_row,
    utc_now_iso,
)
from basis.services.errors import AdminError
from basis.services.tenancy.admin.passwords import hash_token
from basis.services.tenancy.admin.persistence import api_tokens as api_token_persist
from basis.services.tenancy.admin.persistence import audit as audit_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


class ApiTokensAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def create_api_token(
        self,
        actor: User,
        *,
        name: str,
        scope: str,
        workspace_ids: list[str],
        expires_at: str | None = None,
        allowed_operations: list[str] | None = None,
        mcp_allowed_operations: list[str] | None = None,
        http_allowed_operations: list[str] | None = None,
    ) -> tuple[ApiTokenRecord, str]:
        from basis.services.tenancy.admin.admin_types import secrets_token

        name = name.strip()
        if not name or len(name) > 64:
            raise AdminError(422, "bad_name", "令牌名称需要 1 到 64 个字符")
        if scope not in {"read", "write"}:
            raise AdminError(422, "bad_scope", "scope 必须是 read 或 write")
        if not workspace_ids:
            raise AdminError(422, "bad_workspace_ids", "至少选择一个工作区")
        from basis.services.tenancy.admin.api_token_grants import encode_operation_grants_json

        if allowed_operations is not None and mcp_allowed_operations is None and http_allowed_operations is None:
            mcp_allowed_operations = allowed_operations
            http_allowed_operations = allowed_operations

        def _normalize_ops(ops: list[str] | None, field: str) -> list[str] | None:
            if ops is None:
                return None
            cleaned = sorted({str(op).strip() for op in ops if str(op).strip()})
            if len(cleaned) > 256:
                raise AdminError(422, "bad_allowed_operations", f"{field} 操作列表过长（最多 256 项）")
            return cleaned or None

        mcp_ops = _normalize_ops(mcp_allowed_operations, "MCP")
        http_ops = _normalize_ops(http_allowed_operations, "OpenAPI")
        allowed_json = encode_operation_grants_json(
            mcp_allowed_operations=mcp_ops,
            http_allowed_operations=http_ops,
        )
        cleaned: list[str] = []
        for workspace_id in workspace_ids:
            self._store._workspaces.get_workspace_for(actor, workspace_id, "viewer")
            if workspace_id not in cleaned:
                cleaned.append(workspace_id)
        token_id = str(uuid.uuid4())
        plaintext = secrets_token()
        now = utc_now_iso()
        with self._store._lock:
            conn = self._store._conn
            api_token_persist.insert_api_token(
                conn,
                token_id=token_id,
                token_hash=hash_token(plaintext),
                token_secret=plaintext,
                user_id=actor.id,
                name=name,
                scope=scope,
                workspace_ids_json=json.dumps(cleaned, ensure_ascii=False),
                allowed_operations_json=allowed_json,
                created_at=now,
                expires_at=expires_at,
            )
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="api_token.created",
                target_type="api_token",
                target_id=token_id,
                detail={
                    "name": name,
                    "scope": scope,
                    "workspace_ids": cleaned,
                    "operation_grants": json.loads(allowed_json) if allowed_json else None,
                },
            )
            conn.commit()
            row = api_token_persist.fetch_api_token(conn, token_id)
        return api_token_from_row(row), plaintext

    def list_api_tokens(self, actor: User) -> list[ApiTokenRecord]:
        with self._store._lock:
            rows = api_token_persist.list_api_tokens_for_user(self._store._conn, actor.id)
        return [api_token_from_row(row) for row in rows]

    def revoke_api_token(self, actor: User, token_id: str) -> None:
        with self._store._lock:
            conn = self._store._conn
            row = api_token_persist.fetch_api_token(conn, token_id)
            if row is None:
                raise AdminError(404, "not_found", "令牌不存在")
            if row["user_id"] != actor.id and not actor.is_admin:
                raise AdminError(403, "forbidden", "没有权限")
            if row["revoked_at"] is not None:
                return
            api_token_persist.revoke_api_token(conn, token_id, utc_now_iso())
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="api_token.revoked",
                target_type="api_token",
                target_id=token_id,
                detail={},
            )
            conn.commit()

    def delete_api_token(self, actor: User, token_id: str) -> None:
        with self._store._lock:
            conn = self._store._conn
            row = api_token_persist.fetch_api_token(conn, token_id)
            if row is None:
                raise AdminError(404, "not_found", "令牌不存在")
            if row["user_id"] != actor.id and not actor.is_admin:
                raise AdminError(403, "forbidden", "没有权限")
            api_token_persist.delete_api_token(conn, token_id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="api_token.deleted",
                target_type="api_token",
                target_id=token_id,
                detail={},
            )
            conn.commit()

    def resolve_api_token(self, token: str) -> tuple[User, ApiTokenRecord] | None:
        from basis.services.tenancy.admin.admin_types import User as UserType

        digest = hash_token(token)
        with self._store._lock:
            conn = self._store._conn
            row = api_token_persist.resolve_api_token_row(conn, digest)
            if row is None:
                return None
            if row["revoked_at"] is not None:
                return None
            expires_at = row["expires_at"]
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp <= datetime.now(timezone.utc):
                        return None
                except ValueError:
                    pass
            api_token_persist.touch_api_token_last_used(conn, row["id"])
            conn.commit()
        user = UserType(
            id=row["uid"],
            email=row["email"],
            display_name=row["display_name"],
            is_admin=bool(row["is_admin"]),
            deactivated_at=row["deactivated_at"],
            created_at=row["user_created_at"],
        )
        record = api_token_from_row(row)
        return user, record

    def api_token_allows_workspace(self, record: ApiTokenRecord, workspace_id: str) -> bool:
        return workspace_id in record.workspace_ids
