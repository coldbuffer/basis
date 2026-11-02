"""Organization email-domain auth policy gates (F-ACC-07)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.errors import AdminError

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore

ORG_AUTH_POLICIES = frozenset({"password_allowed", "sso_preferred", "sso_required"})


def assert_local_login_allowed(store: AdminStore, email: str) -> None:
    """Block password / magic-link when org policy requires SSO."""
    org = store.resolve_org_by_email_domain(email.strip())
    if org is None:
        return
    if store.get_org_oidc_config(org.id) is None:
        return
    if org.auth_policy == "sso_required":
        raise AdminError(
            403,
            "sso_required",
            "该邮箱域名需使用企业 SSO 登录",
        )
