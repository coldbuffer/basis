"""User administration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.tenancy.admin.admin_types import (
    User,
    check_password,
    clean_email,
    clean_name,
    require_system_admin,
    user_from_row,
    utc_now_iso,
)
from basis.services.errors import AdminError
from basis.services.tenancy.admin.persistence import audit as audit_persist
from basis.services.tenancy.admin.persistence import users as users_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


class UsersAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._store._lock:
            row = users_persist.fetch_user(self._store._conn, user_id)
        if row is None:
            return None
        return user_from_row(row)

    def list_users(self, *, deactivated: bool = False) -> list[User]:
        with self._store._lock:
            rows = users_persist.list_users(self._store._conn, deactivated=deactivated)
        return [user_from_row(row) for row in rows]

    def create_user(
        self,
        actor: User,
        email: str,
        password: str,
        display_name: str,
        *,
        is_admin: bool = False,
    ) -> User:
        require_system_admin(actor)
        email = clean_email(email)
        display_name = clean_name(display_name, "显示名")
        check_password(password)
        with self._store._lock:
            conn = self._store._conn
            if users_persist.active_by_email(conn, email) is not None:
                raise AdminError(409, "email_taken", "这个邮箱已经注册")
            user = self._store._insert_user(email, password, display_name, is_admin=is_admin)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="user.created",
                target_type="user",
                target_id=user.id,
                detail={"email": email, "is_admin": is_admin},
            )
            conn.commit()
        return user

    def deactivate_user(self, actor: User, target_id: str) -> None:
        require_system_admin(actor)
        with self._store._lock:
            conn = self._store._conn
            target = users_persist.fetch_user(conn, target_id)
            if target is None or target["deactivated_at"] is not None:
                raise AdminError(404, "not_found", "用户不存在")
            if target["is_admin"] and users_persist.active_admin_count(conn) <= 1:
                raise AdminError(409, "last_admin", "不能停用最后一个管理员")
            if target["id"] == actor.id:
                raise AdminError(409, "cannot_deactivate_self", "不能停用自己")
            users_persist.deactivate_user(conn, target_id, utc_now_iso())
            users_persist.delete_session_tokens_for_user(conn, target_id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="user.deactivated",
                target_type="user",
                target_id=target_id,
                detail={},
            )
            conn.commit()

    def reactivate_user(self, actor: User, target_id: str) -> None:
        require_system_admin(actor)
        with self._store._lock:
            conn = self._store._conn
            target = users_persist.fetch_user(conn, target_id)
            if target is None or target["deactivated_at"] is None:
                raise AdminError(404, "not_found", "没有已停用的用户")
            taken = users_persist.active_by_email(conn, target["email"])
            if taken is not None:
                raise AdminError(409, "email_taken", "这个邮箱已被另一个在用账号占用")
            users_persist.reactivate_user(conn, target_id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="user.reactivated",
                target_type="user",
                target_id=target_id,
                detail={},
            )
            conn.commit()
