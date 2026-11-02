"""Admin row DTOs, constants, and row mappers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from basis.services.errors import AdminError

from basis.services.knowledge.models import WORKSPACE_ROLES, ROLE_RANK

ORG_ROLES = frozenset({"owner", "admin", "member"})
ORG_ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def secrets_token() -> str:
    from basis.services.tenancy.admin.passwords import new_token

    return new_token()


@dataclass(frozen=True)
class User:
    id: str
    email: str
    display_name: str
    is_admin: bool
    deactivated_at: str | None
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "is_admin": self.is_admin,
            "deactivated_at": self.deactivated_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ApiTokenRecord:
    id: str
    user_id: str
    name: str
    scope: str
    workspace_ids: tuple[str, ...]
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    revoked_at: str | None
    token_secret: str | None
    mcp_allowed_operations: frozenset[str] | None = None
    http_allowed_operations: frozenset[str] | None = None

    def public(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "scope": self.scope,
            "workspace_ids": list(self.workspace_ids),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "revoked_at": self.revoked_at,
        }
        if self.mcp_allowed_operations is not None:
            payload["mcp_allowed_operations"] = sorted(self.mcp_allowed_operations)
        if self.http_allowed_operations is not None:
            payload["http_allowed_operations"] = sorted(self.http_allowed_operations)
        if self.revoked_at is None and self.token_secret:
            payload["secret"] = self.token_secret
        return payload


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    description: str
    visibility: str
    created_by: str
    created_at: str
    organization_id: str | None = None

    def public(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "visibility": self.visibility,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }
        if self.organization_id:
            payload["organization_id"] = self.organization_id
        return payload


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    slug: str
    auth_policy: str
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "auth_policy": self.auth_policy,
            "created_at": self.created_at,
        }


def user_from_row(row: sqlite3.Row | Any) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        is_admin=bool(row["is_admin"]),
        deactivated_at=row["deactivated_at"],
        created_at=row["created_at"],
    )


def workspace_from_row(row: sqlite3.Row | Any) -> Workspace:
    keys = row.keys()
    org_id = row["organization_id"] if "organization_id" in keys else None
    return Workspace(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        visibility=row["visibility"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        organization_id=org_id,
    )


def api_token_from_row(row: sqlite3.Row | Any) -> ApiTokenRecord:
    from basis.services.tenancy.admin.api_token_grants import parse_operation_grants_json

    workspace_ids = json.loads(row["workspace_ids_json"] or "[]")
    if not isinstance(workspace_ids, list):
        workspace_ids = []
    keys = row.keys()
    secret = row["token_secret"] if "token_secret" in keys else None
    raw_allowed = row["allowed_operations_json"] if "allowed_operations_json" in keys else None
    grants = parse_operation_grants_json(raw_allowed)
    return ApiTokenRecord(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        scope=row["scope"],
        workspace_ids=tuple(str(x) for x in workspace_ids),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        last_used_at=row["last_used_at"],
        revoked_at=row["revoked_at"],
        token_secret=secret,
        mcp_allowed_operations=grants.mcp,
        http_allowed_operations=grants.http,
    )


def org_from_row(row: Any) -> Organization:
    return Organization(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        auth_policy=row["auth_policy"],
        created_at=row["created_at"],
    )


def require_system_admin(user: User) -> None:
    if not user.is_admin:
        raise AdminError(403, "forbidden", "需要系统管理员")


def clean_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(email) > 254:
        raise AdminError(422, "bad_email", "邮箱格式不正确")
    return email


def clean_name(value: str, label: str) -> str:
    value = value.strip()
    if not value or len(value) > 64:
        raise AdminError(422, "bad_name", f"{label}需要 1 到 64 个字符")
    return value


def check_password(password: str) -> None:
    if len(password) < 8:
        raise AdminError(422, "password_too_short", "密码至少 8 位")


def visibility(value: str) -> str:
    if value not in {"open", "restricted"}:
        raise AdminError(422, "bad_visibility", "可见性必须是 open 或 restricted")
    return value


def touches_owner(current: str | None, new_role: str) -> bool:
    return new_role == "owner" or current == "owner"
