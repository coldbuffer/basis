from pathlib import Path

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.services.tenancy.admin.store import AdminStore
from basis.services.tenancy.identity.saml_capabilities import saml_sp_available
from basis.app import create_app

_SAMPLE_CERT = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpEWqJzTMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCWxv
Y2FsaG9zdDAeFw0yNTAxMDEwMDAwMDBaFw00NTAxMDEwMDAwMDBaMBQxEjAQBgNV
BAMMCWxvY2FsaG9zdDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABDummyCertFor
TestsOnlyNotValid==
-----END CERTIFICATE-----"""


def _store(tmp_path: Path) -> AdminStore:
    return AdminStore(tmp_path / "basis.db")


def test_org_saml_upsert_and_domain_resolve(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("saml@example.com", "password1", "Saml")
    workspace = admin.create_workspace(user, "Saml Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
        email_domains=["samlco.com"],
    )
    cfg = admin.get_org_saml_config(org_id)
    assert cfg is not None
    assert cfg["idp_entity_id"].startswith("https://")
    match = admin.resolve_org_sso_for_email("user@samlco.com")
    assert match is not None
    assert match[1] == "saml"
    admin.close()


def test_org_sso_options_includes_saml(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("opts2@example.com", "password1", "Opts2")
    workspace = admin.create_workspace(user, "Saml Opts", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
        email_domains=["samlopts.com"],
        enabled=True,
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.get("/api/v1/auth/org-sso-options")
    assert res.status_code == 200
    options = res.json()["options"]
    saml_opts = [o for o in options if o.get("protocol") == "saml"]
    assert len(saml_opts) == 1
    assert "/api/v1/auth/saml/" in saml_opts[0]["login_path"]


def test_org_saml_slo_requires_idp_url(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("slo@example.com", "password1", "Slo")
    workspace = admin.create_workspace(user, "Slo Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    from basis.services.errors import AdminError

    try:
        admin.upsert_org_saml_config(
            user,
            org_id,
            idp_entity_id="https://idp.example.com/metadata",
            idp_sso_url="https://idp.example.com/sso",
            idp_x509_cert=_SAMPLE_CERT,
            slo_enabled=True,
        )
        assert False, "expected AdminError"
    except AdminError as exc:
        assert exc.code == "bad_idp_slo_url"
    admin.close()


def test_org_saml_signing_requires_key_material(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("sign@example.com", "password1", "Sign")
    workspace = admin.create_workspace(user, "Sign Co", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    from basis.services.errors import AdminError

    try:
        admin.upsert_org_saml_config(
            user,
            org_id,
            idp_entity_id="https://idp.example.com/metadata",
            idp_sso_url="https://idp.example.com/sso",
            idp_x509_cert=_SAMPLE_CERT,
            authn_requests_signed=True,
        )
        assert False, "expected AdminError"
    except AdminError as exc:
        assert exc.code == "missing_sp_signing_material"
    admin.close()


def test_org_saml_api_get_includes_slo_urls(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, token = admin.register("api@example.com", "password1", "Api")
    workspace = admin.create_workspace(user, "Api SAML", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
        idp_slo_url="https://idp.example.com/slo",
        slo_enabled=True,
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.get(
        f"/api/v1/orgs/{org_id}/saml",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert body["slo_enabled"] is True
    assert body["idp_slo_url"] == "https://idp.example.com/slo"
    assert "/api/v1/auth/saml/slo" in body["slo_url"]
    assert "logout" in body["logout_url_template"]


def test_logout_returns_saml_logout_url_for_federated_user(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, token = admin.register("fed@example.com", "password1", "Fed")
    workspace = admin.create_workspace(user, "Fed SAML", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
        idp_slo_url="https://idp.example.com/slo",
        slo_enabled=True,
    )
    subject = "fed-user@example.com"
    fed_user, fed_token = admin.login_or_register_federated(
        provider="saml",
        subject=subject,
        email="fed-user@example.com",
        display_name="Fed User",
        organization_id=org_id,
        issuer="https://idp.example.com/metadata",
    )
    _ = fed_user
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {fed_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "saml_logout_url" in body
    assert "name_id=" in body["saml_logout_url"]
    assert "/logout" in body["saml_logout_url"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fed_token}"})
    assert me.status_code == 401


def test_org_saml_logout_requires_slo_enabled(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("logout@example.com", "password1", "Logout")
    workspace = admin.create_workspace(user, "Logout SAML", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    org = admin.get_org_by_id(org_id)
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
        slo_enabled=False,
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.get(
        f"/api/v1/auth/saml/{org.slug}/logout",
        params={"name_id": "user@example.com"},
        follow_redirects=False,
    )
    if not saml_sp_available():
        assert res.status_code == 503
    else:
        assert res.status_code == 400
        assert res.json()["detail"]["code"] == "slo_disabled"


def test_org_saml_start_when_library_missing(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("start@example.com", "password1", "Start")
    workspace = admin.create_workspace(user, "Start SAML", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    org = admin.get_org_by_id(org_id)
    admin.upsert_org_saml_config(
        user,
        org_id,
        idp_entity_id="https://idp.example.com/metadata",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=_SAMPLE_CERT,
    )
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    res = client.get(f"/api/v1/auth/saml/{org.slug}/start", follow_redirects=False)
    if saml_sp_available():
        assert res.status_code in (302, 307)
    else:
        assert res.status_code == 503
