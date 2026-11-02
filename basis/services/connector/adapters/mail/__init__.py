"""IMAP/SMTP mail protocol adapter."""

from basis.services.connector.adapters.mail.adapter import MailAdapter
from basis.services.connector.adapters.mail.credentials import MAIL_CREDENTIAL_READERS

__all__ = ["MailAdapter", "MAIL_CREDENTIAL_READERS"]
