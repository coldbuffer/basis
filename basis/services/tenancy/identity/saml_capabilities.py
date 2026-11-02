"""Optional SAML SP support (python3-saml / OneLogin)."""

from __future__ import annotations


def saml_sp_available() -> bool:
    try:
        import onelogin.saml2.auth  # noqa: F401
    except ImportError:
        return False
    return True
