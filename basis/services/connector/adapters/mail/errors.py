"""Mail (IMAP/SMTP) adapter errors."""

from __future__ import annotations


class MailAdapterError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        super().__init__(message)
