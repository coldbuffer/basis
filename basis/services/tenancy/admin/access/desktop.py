"""Desktop local principal bootstrap."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.tenancy.admin.admin_types import User, secrets_token, user_from_row, utc_now_iso
from basis.services.tenancy.admin.passwords import hash_password
from basis.services.tenancy.admin.persistence import audit as audit_persist
from basis.services.tenancy.admin.persistence import workspaces as workspace_persist
from basis.services.tenancy.admin.persistence import users as users_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore

DESKTOP_USER_ID = "basis-desktop-local"
DESKTOP_EMAIL = "local@basis.desktop"
DESKTOP_DISPLAY_NAME = "Local"


class DesktopAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def commit_transaction(self) -> None:
        with self._store._lock:
            self._store._conn.commit()

    def ensure_desktop_principal(self) -> User:
        existing = self._store._users.get_user_by_id(DESKTOP_USER_ID)
        if existing is not None:
            self._ensure_desktop_default_workspace(existing.id)
            return existing
        password = secrets_token()
        with self._store._lock:
            conn = self._store._conn
            row = users_persist.fetch_user(conn, DESKTOP_USER_ID)
            if row is not None:
                user = user_from_row(row)
                self._ensure_desktop_default_workspace(user.id)
                conn.commit()
                return user
            created_at = utc_now_iso()
            conn.execute(
                """
                INSERT INTO users(id, email, display_name, password_hash, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    DESKTOP_USER_ID,
                    DESKTOP_EMAIL,
                    DESKTOP_DISPLAY_NAME,
                    hash_password(password),
                    1,
                    created_at,
                ),
            )
            org = self._store._organizations.create_organization_locked(
                "本地工作区", owner_user_id=DESKTOP_USER_ID
            )
            workspace_id = self._store._insert_workspace(
                "本地工作区", "", "restricted", DESKTOP_USER_ID, org.id
            )
            self._store._set_member(workspace_id, DESKTOP_USER_ID, "owner", DESKTOP_USER_ID)
            audit_persist.insert_audit(
                conn,
                actor_id=DESKTOP_USER_ID,
                action="auth.desktop_bootstrap",
                target_type="user",
                target_id=DESKTOP_USER_ID,
                detail={"email": DESKTOP_EMAIL},
            )
            conn.commit()
        user = self._store._users.get_user_by_id(DESKTOP_USER_ID)
        assert user is not None
        return user

    def _ensure_desktop_default_workspace(self, user_id: str) -> None:
        with self._store._lock:
            if workspace_persist.workspace_count(self._store._conn) > 0:
                return
            org = self._store._organizations.create_organization_locked(
                "本地工作区", owner_user_id=user_id
            )
            workspace_id = self._store._insert_workspace("本地工作区", "", "restricted", user_id, org.id)
            self._store._set_member(workspace_id, user_id, "owner", user_id)

    def issue_desktop_session_token(self, user: User) -> str:
        with self._store._lock:
            token = self._store._issue_token(user.id)
            self._store._conn.commit()
        return token

    def ensure_oauth_state_secret(self) -> str:
        from basis.services.tenancy.admin.passwords import new_token

        with self._store._lock:
            conn = self._store._conn
            existing = self._store._setting("auth_oauth_state_secret")
            if existing and existing.strip():
                return existing.strip()
            secret = new_token()
            self._store._put_setting("auth_oauth_state_secret", secret)
            conn.commit()
            return secret
