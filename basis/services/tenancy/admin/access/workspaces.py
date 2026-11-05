"""Workspace and membership access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from basis.services.tenancy.admin.admin_types import (
    ROLE_RANK,
    WORKSPACE_ROLES,
    User,
    Workspace,
    clean_name,
    workspace_from_row,
    touches_owner,
    visibility as parse_visibility,
)
from basis.services.errors import AdminError
from basis.services.tenancy.admin.persistence import audit as audit_persist
from basis.services.tenancy.admin.persistence import workspaces as workspace_persist
from basis.services.tenancy.admin.persistence import users as users_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


DEFAULT_WORKSPACE_NAME = "默认工作区"


class WorkspacesAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def list_visible_workspaces(self, user: User) -> list[Workspace]:
        with self._store._lock:
            conn = self._store._conn
            if user.is_admin:
                rows = workspace_persist.list_all_workspaces(conn)
            else:
                rows = workspace_persist.list_visible_workspaces_for_user(conn, user.id)
        return [workspace_from_row(row) for row in rows]

    def list_workspace_ids(self) -> list[str]:
        with self._store._lock:
            return workspace_persist.list_workspace_ids(self._store._conn)

    def provision_default_workspace_locked(self, user: User) -> str:
        """Create a private workspace for a newly registered user. Caller holds the lock and commits."""
        org = self._store._organizations.create_organization_locked(
            DEFAULT_WORKSPACE_NAME, owner_user_id=user.id
        )
        workspace_id = self._store._insert_workspace(
            DEFAULT_WORKSPACE_NAME, "", "restricted", user.id, org.id
        )
        self._store._set_member(workspace_id, user.id, "owner", user.id)
        return workspace_id

    def create_workspace(
        self, actor: User, name: str, description: str | None, visibility: str
    ) -> Workspace:
        name = clean_name(name, "工作区名称")
        vis = parse_visibility(visibility)
        if vis == "open" and not actor.is_admin:
            raise AdminError(403, "forbidden", "只有系统管理员可以创建公开工作区")
        with self._store._lock:
            conn = self._store._conn
            if getattr(self._store._db, "backend", "") == "postgres":
                self._store._organizations.ensure_workspaces_organization_column()
            org = self._store._organizations.create_organization_locked(
                name, owner_user_id=actor.id
            )
            workspace_id = self._store._insert_workspace(
                name, description or "", vis, actor.id, org.id
            )
            self._store._set_member(workspace_id, actor.id, "owner", actor.id)
            workspace = workspace_from_row(
                workspace_persist.fetch_workspace(conn, workspace_id)
            )
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="workspace.created",
                target_type="workspace",
                target_id=workspace_id,
                detail={"name": name},
            )
            conn.commit()
        return workspace

    def get_workspace_for(
        self, user: User, workspace_id: str, minimum: str
    ) -> tuple[Workspace, str]:
        with self._store._lock:
            row = workspace_persist.fetch_workspace(self._store._conn, workspace_id)
            if row is None:
                raise AdminError(404, "not_found", "工作区不存在")
            workspace = workspace_from_row(row)
            role = self._store._access_role(user, workspace)
        if role is None or ROLE_RANK[role] < ROLE_RANK[minimum]:
            raise AdminError(403, "forbidden", "没有权限")
        return workspace, role

    def update_workspace(
        self,
        actor: User,
        workspace_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> Workspace:
        self.get_workspace_for(actor, workspace_id, "admin")
        vis: str | None = None
        if visibility is not None:
            vis = parse_visibility(visibility)
            if vis == "open" and not actor.is_admin:
                raise AdminError(403, "forbidden", "只有系统管理员可以把库改为公开")
        with self._store._lock:
            conn = self._store._conn
            current = workspace_persist.fetch_workspace(conn, workspace_id)
            if current is None:
                raise AdminError(404, "not_found", "工作区不存在")
            workspace_persist.update_workspace(
                conn,
                workspace_id,
                name=clean_name(name, "工作区名称") if name is not None else current["name"],
                description=description if description is not None else current["description"],
                visibility=vis if vis is not None else current["visibility"],
            )
            workspace = workspace_from_row(
                workspace_persist.fetch_workspace(conn, workspace_id)
            )
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="workspace.updated",
                target_type="workspace",
                target_id=workspace_id,
                detail={},
            )
            conn.commit()
        return workspace

    def delete_workspace(self, actor: User, workspace_id: str) -> None:
        _, role = self.get_workspace_for(actor, workspace_id, "admin")
        if role != "owner" and not actor.is_admin:
            raise AdminError(403, "forbidden", "只有所有者或系统管理员可以删除工作区")
        with self._store._lock:
            conn = self._store._conn
            workspace_persist.delete_workspace(conn, workspace_id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="workspace.deleted",
                target_type="workspace",
                target_id=workspace_id,
                detail={},
            )
            conn.commit()

    def list_members(self, actor: User, workspace_id: str) -> list[dict[str, Any]]:
        self.get_workspace_for(actor, workspace_id, "viewer")
        with self._store._lock:
            rows = workspace_persist.list_members(self._store._conn, workspace_id)
        return [
            {
                "user_id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "role": row["role"],
                "joined_at": row["joined_at"],
            }
            for row in rows
        ]

    def set_member_role(self, actor: User, workspace_id: str, target_id: str, role: str) -> None:
        if role not in WORKSPACE_ROLES:
            raise AdminError(422, "bad_role", "角色必须是 owner、admin、editor 或 viewer")
        _, caller_role = self.get_workspace_for(actor, workspace_id, "admin")
        with self._store._lock:
            conn = self._store._conn
            target = users_persist.fetch_user(conn, target_id)
            if target is None or target["deactivated_at"] is not None:
                raise AdminError(404, "not_found", "用户不存在")
            current = workspace_persist.member_role(conn, workspace_id, target_id)
            if touches_owner(current, role) and caller_role != "owner":
                raise AdminError(403, "forbidden", "只有所有者可以授予或取消所有者")
            if (
                current == "owner"
                and role != "owner"
                and workspace_persist.owner_count(conn, workspace_id) <= 1
            ):
                raise AdminError(409, "last_owner", "不能降级最后一个所有者")
            self._store._set_member(workspace_id, target_id, role, actor.id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="member.role_set",
                target_type="workspace",
                target_id=workspace_id,
                detail={"user_id": target_id, "role": role},
            )
            conn.commit()

    def remove_member(self, actor: User, workspace_id: str, target_id: str) -> None:
        _, caller_role = self.get_workspace_for(actor, workspace_id, "admin")
        with self._store._lock:
            conn = self._store._conn
            current = workspace_persist.member_role(conn, workspace_id, target_id)
            if current is None:
                raise AdminError(404, "not_found", "成员不存在")
            if current == "owner":
                if caller_role != "owner" and not actor.is_admin:
                    raise AdminError(403, "forbidden", "只有所有者可以移除所有者")
                if workspace_persist.owner_count(conn, workspace_id) <= 1:
                    raise AdminError(409, "last_owner", "不能移除最后一个所有者")
            workspace_persist.remove_member(conn, workspace_id, target_id)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="member.removed",
                target_type="workspace",
                target_id=workspace_id,
                detail={"user_id": target_id},
            )
            conn.commit()
