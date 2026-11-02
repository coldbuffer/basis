"""Mailbox credentials (ported from OpenConnector mail profiles)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MailCredential:
    email: str
    authorization_code: str
    imap_host: str
    smtp_host: str
    smtp_port: int = 465
    smtp_secure: bool = True


CredentialReader = Callable[[dict[str, Any]], MailCredential]


def read_qq_mail_credential(values: dict[str, Any]) -> MailCredential:
    email = str(values.get("email") or "").strip()
    authorization_code = str(
        values.get("authorizationCode") or values.get("authorization_code") or ""
    ).strip()
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1] or any(c.isspace() for c in email):
        raise ValueError("QQ Mail email must be a valid email address.")
    if len(authorization_code) != 16:
        raise ValueError("QQ Mail authorization code must be 16 characters.")
    return MailCredential(
        email=email,
        authorization_code=authorization_code,
        imap_host="imap.qq.com",
        smtp_host="smtp.qq.com",
    )


MAIL_CREDENTIAL_READERS: dict[str, CredentialReader] = {
    "qq_mail": read_qq_mail_credential,
}


def read_mail_credential(service: str, values: dict[str, Any]) -> MailCredential:
    reader = MAIL_CREDENTIAL_READERS.get(service)
    if reader is None:
        raise ValueError(f"No mail credential profile for service '{service}'")
    return reader(values)
