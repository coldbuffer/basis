from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

import pytest

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore
from basis.services.tenancy.identity.cas_client import cas_validate_url, parse_cas_success


def _store(tmp_path: Path) -> AdminStore:
    return AdminStore(tmp_path / "basis.db")


_SUCCESS_XML = """<?xml version="1.0"?>
<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
  <cas:authenticationSuccess>
    <cas:user>jdoe</cas:user>
    <cas:attributes>
      <cas:email>owner@school.edu</cas:email>
      <cas:name>Jane Doe</cas:name>
    </cas:attributes>
  </cas:authenticationSuccess>
</cas:serviceResponse>
"""


def test_parse_cas_success_reads_email_attribute() -> None:
    subject, email, name = parse_cas_success(_SUCCESS_XML, "email")
    assert subject == "jdoe"
    assert email == "owner@school.edu"
    assert name == "Jane Doe"


def test_parse_cas_success_reads_named_attribute_and_failure() -> None:
    xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
      <cas:authenticationSuccess>
        <cas:user>stu001</cas:user>
        <cas:attributes>
          <cas:attribute name="mail" value="stu001@school.edu"/>
          <cas:attribute name="cn" value="Student One"/>
        </cas:attributes>
      </cas:authenticationSuccess>
    </cas:serviceResponse>"""
    subject, email, name = parse_cas_success(xml, "mail")
    assert subject == "stu001"
    assert email == "stu001@school.edu"
    assert name == "Student One"
    failure = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
      <cas:authenticationFailure code="INVALID_TICKET">bad</cas:authenticationFailure>
    </cas:serviceResponse>"""
    try:
        parse_cas_success(failure, "email")
    except ValueError as exc:
        assert str(exc) == "INVALID_TICKET"
    else:
        raise AssertionError("expected ValueError")


def test_parse_cas_success_uses_username_when_it_is_an_email() -> None:
    xml = """<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
      <cas:authenticationSuccess><cas:user>ada@school.edu</cas:user></cas:authenticationSuccess>
    </cas:serviceResponse>"""
    subject, email, _name = parse_cas_success(xml, "email")
    assert subject == "ada@school.edu"
    assert email == "ada@school.edu"


def test_org_cas_upsert_and_login_redirect(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("owner@school.edu", "password1", "Owner")
    workspace = admin.create_workspace(user, "School", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    admin.upsert_org_cas_config(
        user,
        org_id,
        server_url="https://cas.school.edu/cas/",
        email_domains=["school.edu"],
    )
    org = admin.get_org_by_id(org_id)
    assert org is not None
    slug = org.slug
    resolved = admin.resolve_org_sso_for_email("student@school.edu")
    assert resolved is not None
    assert resolved[1] == "cas"
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    start = client.get(f"/api/v1/auth/cas/{slug}/start", follow_redirects=False)
    assert start.status_code in (302, 307)
    location = start.headers["location"]
    assert location.startswith("https://cas.school.edu/cas/login?")
    service = parse_qs(urlparse(location).query)["service"][0]
    assert f"/api/v1/auth/cas/callback?org={slug}" in service

    with patch(
        "basis.routes.admin.auth.auth_cas.validate_cas_ticket",
        new_callable=AsyncMock,
        return_value=_SUCCESS_XML,
    ):
        callback = client.get(
            "/api/v1/auth/cas/callback",
            params={"org": slug, "ticket": "ST-1"},
            follow_redirects=False,
        )
    assert callback.status_code in (302, 307)
    assert "basis_token=" in callback.headers["location"]


def test_org_cas_custom_paths_change_login_redirect(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("owner@school.edu", "password1", "Owner")
    workspace = admin.create_workspace(user, "School", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    saved = admin.upsert_org_cas_config(
        user,
        org_id,
        server_url="https://sso.example.com",
        login_path="/api/sso_login/",
        validate_path="/api/sso_validate",
        email_domains=["school.edu"],
    )
    assert saved["login_path"] == "/api/sso_login/"
    assert saved["validate_path"] == "/api/sso_validate"
    org = admin.get_org_by_id(org_id)
    assert org is not None
    admin.close()

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    start = client.get(f"/api/v1/auth/cas/{org.slug}/start", follow_redirects=False)
    assert start.status_code in (302, 307)
    assert start.headers["location"].startswith("https://sso.example.com/api/sso_login/?")
    validate = cas_validate_url(
        "https://sso.example.com",
        "https://app.example.com/callback",
        "ST-1",
        "/api/sso_validate",
    )
    assert validate.startswith("https://sso.example.com/api/sso_validate?")
    assert "ticket=ST-1" in validate


def test_org_cas_rejects_absolute_validate_path(tmp_path: Path) -> None:
    admin = _store(tmp_path)
    user, _ = admin.register("owner@school.edu", "password1", "Owner")
    workspace = admin.create_workspace(user, "School", None, "restricted")
    org_id = workspace.organization_id
    assert org_id
    with pytest.raises(AdminError) as raised:
        admin.upsert_org_cas_config(
            user,
            org_id,
            server_url="https://cas.school.edu/cas",
            validate_path="https://evil.example/serviceValidate",
        )
    assert raised.value.code == "bad_cas_path"
    admin.close()
