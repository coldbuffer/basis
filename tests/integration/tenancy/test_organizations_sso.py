from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.services.tenancy.identity.oauth_client import build_oidc_authorize_url
from basis.services.tenancy.admin.store import AdminStore
from basis.app import create_app
def _store(tmp_path: Path) -> AdminStore:
    return AdminStore(tmp_path / "basis.db")


def test_workspace_backfill_creates_organization(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("o@example.com", "password1", "Owner")
    workspace = admin.create_workspace(user, "Demo KB", None, "restricted")
    assert workspace.organization_id
    org = admin.get_org_by_id(workspace.organization_id or "")
    assert org is not None
    assert admin.org_role(org.id, user.id) == "owner"
    admin.close()


def test_org_oidc_upsert_and_slug_login_path(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("admin@example.com", "password1", "Admin")
    workspace = admin.create_workspace(user, "Acme", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_oidc_config(
        user,
        org_id,
        issuer="http://localhost:9000/application/o/basis/",
        client_id="cid",
        client_secret="secret",
        email_domains=["acme.com"],
    )
    cfg = admin.get_org_oidc_config(org_id)
    assert cfg is not None
    assert cfg["client_id"] == "cid"
    org = admin.get_org_by_id(org_id)
    assert org is not None
    resolved = admin.resolve_org_by_email_domain("user@acme.com")
    assert resolved is not None
    assert resolved.id == org_id
    admin.close()


def test_org_sso_options_lists_enabled_orgs(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("opts@example.com", "password1", "Opts")
    workspace = admin.create_workspace(user, "Opts Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_oidc_config(
        user,
        org_id,
        issuer="https://idp.example.com/",
        client_id="cid",
        client_secret="secret",
        email_domains=["optsco.com"],
        enabled=True,
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.get("/api/v1/auth/org-sso-options")
    assert res.status_code == 200
    body = res.json()
    assert len(body["options"]) == 1
    assert body["options"][0]["org_slug"]
    assert "/api/v1/auth/oidc/" in body["options"][0]["login_path"]


def test_build_oidc_authorize_url_encodes_query() -> None:
    url = build_oidc_authorize_url(
        {"authorization_endpoint": "https://idp.example.com/authorize"},
        client_id="cid",
        redirect_uri="http://127.0.0.1:8090/api/v1/auth/oidc/callback",
        scope="openid email profile",
        state="signed-state",
    )
    assert url.startswith("https://idp.example.com/authorize?")
    assert "client_id=cid" in url
    assert "response_type=code" in url
    assert "state=signed-state" in url


def test_org_oidc_start_redirects_to_idp(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("start@example.com", "password1", "Start")
    workspace = admin.create_workspace(user, "Start Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_oidc_config(
        user,
        org_id,
        issuer="https://idp.example.com/",
        client_id="cid",
        client_secret="secret",
        email_domains=["startco.com"],
        enabled=True,
    )
    org = admin.get_org_by_id(org_id)
    assert org is not None
    slug = org.slug
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    metadata = {
        "authorization_endpoint": "https://idp.example.com/authorize",
        "token_endpoint": "https://idp.example.com/token",
    }
    with patch(
        "basis.routes.admin.auth.auth_oidc.fetch_oidc_metadata",
        new_callable=AsyncMock,
        return_value=metadata,
    ):
        res = client.get(f"/api/v1/auth/oidc/{slug}/start", follow_redirects=False)
    assert res.status_code in (302, 307)
    location = res.headers["location"]
    assert location.startswith("https://idp.example.com/authorize")
    assert "client_id=cid" in location
    assert "redirect_uri=" in location
    assert "state=" in location


def test_org_sso_hint_by_email_domain(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("hint@example.com", "password1", "Hint")
    workspace = admin.create_workspace(user, "Hint Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_oidc_config(
        user,
        org_id,
        issuer="https://idp.example.com/",
        client_id="cid",
        client_secret="secret",
        email_domains=["hintco.com"],
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    miss = client.get("/api/v1/auth/org-sso-hint", params={"email": "x@other.com"})
    assert miss.status_code == 200
    assert miss.json()["available"] is False

    hit = client.get("/api/v1/auth/org-sso-hint", params={"email": "user@hintco.com"})
    assert hit.status_code == 200
    body = hit.json()
    assert body["available"] is True
    assert body["org_slug"]
    assert "/api/v1/auth/oidc/" in body["login_path"]


def test_sso_required_blocks_password_login(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("owner@example.com", "password1", "Owner")
    workspace = admin.create_workspace(user, "Strict Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_oidc_config(
        user,
        org_id,
        issuer="https://idp.example.com/",
        client_id="cid",
        client_secret="secret",
        email_domains=["strictco.com"],
        auth_policy="sso_required",
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "emp@strictco.com", "password": "password1"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "sso_required"

    magic = client.post(
        "/api/v1/auth/magic-link/request",
        json={"email": "emp@strictco.com"},
    )
    assert magic.status_code in (403, 404, 503)
    if magic.status_code == 403:
        assert magic.json()["detail"]["code"] == "sso_required"


def test_magic_link_login(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    token = admin.create_magic_link("magic@example.com")
    user, session = admin.consume_magic_link(token)
    assert user.email == "magic@example.com"
    assert admin.user_by_token(session) is not None
    admin.close()
