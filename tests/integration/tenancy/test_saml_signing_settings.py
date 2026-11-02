"""SAML AuthnRequest signing settings."""

from basis.services.tenancy.identity.saml_client import build_saml_settings


def test_build_saml_settings_unsigned_by_default() -> None:
    settings = build_saml_settings(
        sp_entity_id="https://app/sp",
        acs_url="https://app/acs",
        idp_entity_id="https://idp/metadata",
        idp_sso_url="https://idp/sso",
        idp_x509_cert="CERT",
    )
    assert settings["security"]["authnRequestsSigned"] is False
    assert "privateKey" not in settings["sp"]


def test_build_saml_settings_signed_requires_material() -> None:
    settings = build_saml_settings(
        sp_entity_id="https://app/sp",
        acs_url="https://app/acs",
        idp_entity_id="https://idp/metadata",
        idp_sso_url="https://idp/sso",
        idp_x509_cert="CERT",
        authn_requests_signed=True,
        sp_x509_cert="-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----",
        sp_private_key="-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
    )
    assert settings["security"]["authnRequestsSigned"] is True
    assert "privateKey" in settings["sp"]


def test_build_saml_settings_slo_when_enabled() -> None:
    settings = build_saml_settings(
        sp_entity_id="https://app/sp",
        acs_url="https://app/acs",
        idp_entity_id="https://idp/metadata",
        idp_sso_url="https://idp/sso",
        idp_x509_cert="CERT",
        slo_enabled=True,
        idp_slo_url="https://idp/slo",
        sp_slo_url="https://app/slo",
    )
    assert "singleLogoutService" in settings["idp"]
    assert settings["idp"]["singleLogoutService"]["url"] == "https://idp/slo"
    assert settings["sp"]["singleLogoutService"]["url"] == "https://app/slo"


def test_build_saml_settings_slo_omitted_when_disabled() -> None:
    settings = build_saml_settings(
        sp_entity_id="https://app/sp",
        acs_url="https://app/acs",
        idp_entity_id="https://idp/metadata",
        idp_sso_url="https://idp/sso",
        idp_x509_cert="CERT",
        slo_enabled=False,
        idp_slo_url="https://idp/slo",
        sp_slo_url="https://app/slo",
    )
    assert "singleLogoutService" not in settings["idp"]
    assert "singleLogoutService" not in settings["sp"]
