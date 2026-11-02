from __future__ import annotations

from unittest.mock import MagicMock

from basis.services.connector.adapters.mail.actions import execute_mail_action
from basis.services.connector.adapters.mail.credentials import read_qq_mail_credential
from basis.services.connector.adapters.mail.protocol import ImapSmtpProtocol
from basis.services.connector.manifest.manifest_schema import MailProcedureExecutorSpec


def test_read_qq_mail_credential_validates() -> None:
    cred = read_qq_mail_credential(
        {"email": "user@qq.com", "authorizationCode": "1234567890123456"}
    )
    assert cred.imap_host == "imap.qq.com"
    assert cred.smtp_host == "smtp.qq.com"


def test_list_folders_via_mail_action_mocked() -> None:
    protocol = MagicMock(spec=ImapSmtpProtocol)
    protocol.list_folders.return_value = []
    out = execute_mail_action(
        "qq_mail",
        "list_folders",
        {"email": "user@qq.com", "authorizationCode": "1234567890123456"},
        {},
        protocol=protocol,
    )
    assert out == {"folders": []}
    protocol.list_folders.assert_called_once()


def test_qq_mail_shipped_manifest_includes_mail_procedures() -> None:
    """Shipped ``providers/qq_mail.yaml`` is the CI source of truth (no OpenConnector tree)."""
    from basis.services.connector.catalog import ConnectorCatalog

    m = ConnectorCatalog.load_from_directory().get("qq_mail")
    assert m is not None
    procs = m.procedure_actions()
    assert len(procs) >= 10
    assert all(p.mail is not None for p in procs)
    assert any(p.mail and p.mail.action == "list_folders" for p in procs if p.mail)


def test_mail_procedure_spec_round_trip() -> None:
    spec = MailProcedureExecutorSpec(action="list_folders")
    assert spec.action == "list_folders"
