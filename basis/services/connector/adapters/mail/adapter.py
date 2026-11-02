"""BOCP mail adapter (IMAP/SMTP procedures + CHECK)."""

from __future__ import annotations

from typing import Any

from basis.services.connector.adapters.mail.actions import execute_mail_action
from basis.services.connector.adapters.mail.credentials import read_mail_credential
from basis.services.connector.adapters.mail.protocol import ImapSmtpProtocol
from basis.services.connector.vault.auth_vault import StoredConnection
from basis.services.connector.manifest.manifest_schema import ConnectorManifest, ProcedureActionSpec


class MailAdapter:
    def __init__(self, *, protocol: ImapSmtpProtocol | None = None) -> None:
        self._protocol = protocol or ImapSmtpProtocol()

    def check_connection(
        self, manifest: ConnectorManifest, connection: StoredConnection
    ) -> dict[str, Any]:
        cred = read_mail_credential(manifest.service, connection.credentials)
        self._protocol.validate_imap(cred)
        self._protocol.validate_smtp(cred)
        normalized = cred.email.lower()
        return {
            "ok": True,
            "account_id": normalized,
            "display_name": cred.email,
            "email": normalized,
            "imap_host": cred.imap_host,
            "smtp_host": cred.smtp_host,
        }

    def execute_procedure(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
        procedure: ProcedureActionSpec,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if procedure.mail is None:
            raise ValueError(f"Procedure '{procedure.id}' is not a mail procedure")
        return execute_mail_action(
            manifest.service,
            procedure.mail.action,
            connection.credentials,
            arguments,
            protocol=self._protocol,
        )
