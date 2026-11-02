"""Session auth: register, login, logout."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from basis.services.tenancy.admin.admin_types import (
    User,
    check_password,
    clean_email,
    clean_name,
    secrets_token,
    user_from_row,
)
from basis.services.errors import AdminError
from basis.services.tenancy.admin.passwords import hash_token, verify_password
from basis.services.tenancy.admin.persistence import audit as audit_persist
from basis.services.tenancy.admin.persistence import settings as settings_persist
from basis.services.tenancy.admin.persistence import users as users_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


class AuthAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def register(self, email: str, password: str, display_name: str) -> tuple[User, str]:
        email = clean_email(email)
        display_name = clean_name(display_name, "显示名")
        check_password(password)
        with self._store._lock:
            conn = self._store._conn
            first = users_persist.user_count(conn) == 0
            if not first and settings_persist.get_setting(conn, "open_registration") != "true":
                raise AdminError(403, "registration_closed", "注册已关闭")
            if users_persist.active_by_email(conn, email) is not None:
                raise AdminError(409, "email_taken", "这个邮箱已经注册")
            user = self._store._insert_user(email, password, display_name, is_admin=first)
            token = self._store._issue_token(user.id)
            if first:
                org = self._store._organizations.create_organization_locked(
                    "公共工作区", owner_user_id=user.id
                )
                workspace_id = self._store._insert_workspace("公共工作区", "", "open", user.id, org.id)
                self._store._set_member(workspace_id, user.id, "owner", user.id)
            audit_persist.insert_audit(
                conn,
                actor_id=user.id,
                action="auth.register",
                target_type="user",
                target_id=user.id,
                detail={"email": email},
            )
            conn.commit()
        return user, token

    def login(self, email: str, password: str) -> tuple[User, str]:
        email = email.strip().lower()
        with self._store._lock:
            conn = self._store._conn
            row = users_persist.active_by_email(conn, email)
            if row is None or not verify_password(password, row["password_hash"]):
                reason = "unknown_email" if row is None else "bad_password"
                audit_persist.insert_audit(
                    conn,
                    actor_id=None,
                    action="auth.login_failed",
                    target_type="user",
                    target_id=None,
                    detail={"email": email, "reason": reason},
                )
                conn.commit()
                raise AdminError(401, "invalid_credentials", "邮箱或密码不正确")
            user = user_from_row(row)
            token = self._store._issue_token(user.id)
            audit_persist.insert_audit(
                conn,
                actor_id=user.id,
                action="auth.login",
                target_type="user",
                target_id=user.id,
                detail={},
            )
            conn.commit()
        return user, token

    def logout(self, token: str, user_id: str) -> None:
        with self._store._lock:
            conn = self._store._conn
            users_persist.delete_session_token(conn, hash_token(token))
            audit_persist.insert_audit(
                conn,
                actor_id=user_id,
                action="auth.logout",
                target_type="user",
                target_id=user_id,
                detail={},
            )
            conn.commit()

    def user_by_token(self, token: str) -> User | None:
        with self._store._lock:
            row = users_persist.user_by_session_token(self._store._conn, hash_token(token))
        return user_from_row(row) if row else None
