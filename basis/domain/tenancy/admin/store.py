"""Accounts, workspaces, membership, settings, and the audit log."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from basis.infra.runtime.database import Database, get_sqlite_database
from basis.domain.tenancy.admin.access.api_tokens import ApiTokensAccess
from basis.domain.tenancy.admin.access.audit import AuditAccess
from basis.domain.tenancy.admin.access.auth import AuthAccess
from basis.domain.tenancy.admin.access.desktop import DesktopAccess
from basis.domain.tenancy.admin.access.workspaces import WorkspacesAccess
from basis.domain.tenancy.admin.access.models import ModelsAccess
from basis.domain.tenancy.admin.access.organizations import OrganizationsAccess
from basis.domain.tenancy.admin.access.settings import SettingsAccess
from basis.domain.tenancy.admin.access.users import UsersAccess
from basis.domain.tenancy.admin.admin_types import (
    ROLE_RANK,
    ApiTokenRecord,
    Workspace,
    User,
    require_system_admin,
    secrets_token,
    user_from_row,
    utc_now_iso,
)
from basis.domain.tenancy.admin.persistence import audit as audit_persist
from basis.domain.tenancy.admin.persistence import workspaces as workspace_persist
from basis.domain.tenancy.admin.persistence import settings as settings_persist
from basis.domain.tenancy.admin.persistence import users as users_persist
from basis.domain.tenancy.admin.passwords import hash_token

_now = utc_now_iso
_user_from_row = user_from_row
_require_system_admin = require_system_admin


def _admin_access_delegate(access_attr: str, method_name: str):
    def _wrapped(self, *args, **kwargs):
        return getattr(getattr(self, access_attr), method_name)(*args, **kwargs)

    _wrapped.__name__ = method_name
    _wrapped.__qualname__ = f"AdminStore.{method_name}"
    return _wrapped


class AdminStore:
    def __init__(self, path: Path | Database) -> None:
        if isinstance(path, Database):
            self._db = path
            self._owns_db_ref = False
        else:
            self._db = get_sqlite_database(path)
            self._owns_db_ref = True
        self._lock = self._db.lock
        self._conn = self._db.conn
        self._auth = AuthAccess(self)
        self._users = UsersAccess(self)
        self._api_tokens = ApiTokensAccess(self)
        self._workspaces = WorkspacesAccess(self)
        self._models = ModelsAccess(self)
        self._settings = SettingsAccess(self)
        self._audit_access = AuditAccess(self)
        self._organizations = OrganizationsAccess(self)
        self._desktop = DesktopAccess(self)
        if getattr(self._db, "backend", "") == "postgres":
            self._organizations.ensure_workspaces_organization_column()
            self._organizations.ensure_workspace_organization_links()

    def close(self) -> None:
        if self._owns_db_ref:
            self._db.release()

    def _setting(self, key: str) -> str | None:
        return settings_persist.get_setting(self._conn, key)

    def _put_setting(self, key: str, value: str) -> None:
        settings_persist.put_setting(self._conn, key, value)

    def _audit(
        self,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str | None,
        detail: dict[str, Any],
    ) -> None:
        audit_persist.insert_audit(
            self._conn,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )

    def _insert_user(self, email: str, password: str, display_name: str, *, is_admin: bool) -> User:
        return users_persist.insert_user(
            self._conn,
            email=email,
            password=password,
            display_name=display_name,
            is_admin=is_admin,
            user_id=str(uuid.uuid4()),
        )

    def _issue_token(self, user_id: str) -> str:
        token = secrets_token()
        users_persist.issue_session_token(self._conn, hash_token(token), user_id)
        return token

    def _insert_workspace(
        self,
        name: str,
        description: str,
        visibility: str,
        created_by: str,
        organization_id: str,
    ) -> str:
        return workspace_persist.insert_workspace(
            self._conn,
            workspace_id=str(uuid.uuid4()),
            name=name,
            description=description,
            visibility=visibility,
            created_by=created_by,
            organization_id=organization_id,
        )

    def _set_member(self, workspace_id: str, user_id: str, role: str, added_by: str | None) -> None:
        workspace_persist.set_member(self._conn, workspace_id, user_id, role, added_by)

    def _access_role(self, user: User, workspace: Workspace) -> str | None:
        member = workspace_persist.member_role(self._conn, workspace.id, user.id)
        if member == "owner":
            return "owner"
        if user.is_admin:
            return "admin"
        if member:
            return member
        if workspace.visibility == "open":
            return "viewer"
        return None

    def default_auth_public_url(self) -> str:
        return "http://127.0.0.1:8090"

    def default_auth_web_origin(self) -> str:
        return "http://localhost:5173"

    def build_auth_settings_raw(
        self,
        *,
        default_public_url: str | None = None,
        default_web_origin: str | None = None,
    ) -> dict[str, Any]:
        from basis.domain.tenancy.admin.auth_platform import build_auth_settings_raw

        return build_auth_settings_raw(
            self,
            default_public_url=default_public_url or self.default_auth_public_url(),
            default_web_origin=default_web_origin or self.default_auth_web_origin(),
        )

    def get_access_settings(
        self,
        *,
        default_public_url: str | None = None,
        default_web_origin: str | None = None,
    ) -> dict[str, Any]:
        from basis.domain.tenancy.admin.auth_platform import get_access_settings

        return get_access_settings(
            self,
            default_public_url=default_public_url or self.default_auth_public_url(),
            default_web_origin=default_web_origin or self.default_auth_web_origin(),
        )

    def update_access_settings(
        self,
        actor: User,
        body: dict[str, Any],
        *,
        default_public_url: str | None = None,
        default_web_origin: str | None = None,
    ) -> dict[str, Any]:
        from basis.domain.tenancy.admin.auth_platform import update_access_settings

        return update_access_settings(
            self,
            actor,
            body,
            default_public_url=default_public_url or self.default_auth_public_url(),
            default_web_origin=default_web_origin or self.default_auth_web_origin(),
        )


for _name in ("register", "login", "logout", "user_by_token"):
    setattr(AdminStore, _name, _admin_access_delegate("_auth", _name))

for _name in ("get_user_by_id", "list_users", "create_user", "deactivate_user", "reactivate_user"):
    setattr(AdminStore, _name, _admin_access_delegate("_users", _name))

for _name in (
    "create_api_token",
    "list_api_tokens",
    "revoke_api_token",
    "delete_api_token",
    "resolve_api_token",
    "api_token_allows_workspace",
):
    setattr(AdminStore, _name, _admin_access_delegate("_api_tokens", _name))

for _name in (
    "list_visible_workspaces",
    "list_workspace_ids",
    "create_workspace",
    "get_workspace_for",
    "update_workspace",
    "delete_workspace",
    "list_members",
    "set_member_role",
    "remove_member",
):
    setattr(AdminStore, _name, _admin_access_delegate("_workspaces", _name))

for _name in (
    "list_configured_models",
    "add_configured_model",
    "add_configured_models_batch",
    "upsert_kind_endpoint",
    "delete_configured_model",
    "patch_configured_model",
    "get_chat_llm_settings",
    "get_chat_llm_settings_for_entry",
    "list_public_llm_endpoints",
    "get_embed_settings",
    "get_stored_model_api_key",
    "get_stored_model_api_key_for_probe",
):
    setattr(AdminStore, _name, _admin_access_delegate("_models", _name))

for _name in (
    "get_platform_allowed_providers",
    "upsert_platform_allowed_providers",
    "get_settings",
    "update_settings",
):
    setattr(AdminStore, _name, _admin_access_delegate("_settings", _name))

for _name in ("list_audit", "list_audit_for_workspace", "record_audit"):
    setattr(AdminStore, _name, _admin_access_delegate("_audit_access", _name))

for _name in (
    "list_orgs_for_user",
    "list_all_organizations",
    "ensure_workspaces_organization_column",
    "ensure_workspace_organization_links",
    "reconcile_organization_memberships",
    "ensure_default_organization",
    "prepare_organization_sso_directory",
    "get_org_by_slug",
    "get_org_by_id",
    "org_role",
    "require_org_admin",
    "resolve_org_sso_for_email",
    "resolve_org_by_email_domain",
    "list_enabled_org_sso_public",
    "get_org_oidc_settings",
    "get_org_oidc_config",
    "upsert_org_oidc_config",
    "get_org_saml_settings",
    "get_org_saml_runtime_config",
    "get_org_saml_config",
    "upsert_org_saml_config",
    "login_or_register_federated",
    "saml_logout_hint_for_user",
    "create_magic_link",
    "consume_magic_link",
):
    setattr(AdminStore, _name, _admin_access_delegate("_organizations", _name))

for _name in (
    "commit_transaction",
    "ensure_desktop_principal",
    "issue_desktop_session_token",
    "ensure_oauth_state_secret",
):
    setattr(AdminStore, _name, _admin_access_delegate("_desktop", _name))
