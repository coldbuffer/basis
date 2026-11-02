"""Send magic-link emails (SMTP) or log in dev."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from basis.services.tenancy.identity.settings import AuthSettings

logger = logging.getLogger(__name__)


def deliver_magic_link(settings: AuthSettings, *, email: str, link: str) -> None:
    if settings.magic_link_log or not settings.smtp_enabled:
        logger.info("Magic link for %s: %s", email, link)
        if not settings.smtp_enabled:
            return
    msg = EmailMessage()
    msg["Subject"] = "Basis login link"
    msg["From"] = settings.magic_link_from_email or "noreply@basis.local"
    msg["To"] = email
    msg.set_content(f"Sign in to Basis (link expires in 15 minutes):\n\n{link}\n")
    assert settings.smtp_host
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
