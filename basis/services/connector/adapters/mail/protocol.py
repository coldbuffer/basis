"""IMAP/SMTP mail protocol (stdlib; aligned with OpenConnector mail/imap-smtp)."""

from __future__ import annotations

import base64
import email
import imaplib
import re
import smtplib
import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Iterator

from basis.services.connector.adapters.mail.credentials import MailCredential
from basis.services.connector.adapters.mail.errors import MailAdapterError

MAIL_IMAP_PORT = 993
MAIL_SMTP_PORT = 465
MAIL_MESSAGE_FETCH_BYTE_LIMIT = 5 * 1024 * 1024
MAIL_ATTACHMENT_BYTE_LIMIT = 25 * 1024 * 1024
MAIL_CONNECTION_TIMEOUT_SEC = 30


def _decode_mime_header(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(make_header(decode_header(value)))
    except (email.errors.HeaderParseError, UnicodeError):
        return value


def _address_dict(raw: str | None) -> dict[str, str | None] | None:
    if not raw:
        return None
    name, addr = parseaddr(raw)
    return {"name": _decode_mime_header(name) or None, "email": addr or None}


def _addresses_from_header(msg: email.message.Message, key: str) -> list[dict[str, str | None]]:
    raw = msg.get(key)
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", str(raw))]
    out: list[dict[str, str | None]] = []
    for part in parts:
        if not part:
            continue
        parsed = _address_dict(part)
        if parsed:
            out.append(parsed)
    return out


@dataclass
class MailFolder:
    path: str
    name: str
    delimiter: str | None
    flags: list[str]
    special_use: str | None


class ImapSmtpProtocol:
    def validate_imap(self, credential: MailCredential) -> None:
        with self._imap(credential) as client:
            client.list()

    def validate_smtp(self, credential: MailCredential) -> None:
        with self._smtp(credential) as smtp:
            smtp.noop()

    def list_folders(self, credential: MailCredential) -> list[MailFolder]:
        with self._imap(credential) as client:
            status, data = client.list()
            if status != "OK" or not data:
                return []
            folders: list[MailFolder] = []
            for line in data:
                if not isinstance(line, bytes):
                    continue
                decoded = line.decode("utf-8", errors="replace")
                match = re.match(
                    r'\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]*)"\s+(?P<path>.+)$',
                    decoded.strip(),
                )
                if not match:
                    continue
                flags_raw = match.group("flags") or ""
                flags = [f.strip() for f in flags_raw.replace("\\", "").split() if f.strip()]
                delim = match.group("delim") or None
                path = match.group("path").strip().strip('"')
                name = path.split(delim)[-1] if delim and delim in path else path
                folders.append(
                    MailFolder(
                        path=path,
                        name=name,
                        delimiter=delim,
                        flags=flags,
                        special_use=None,
                    )
                )
            return folders

    def search_summaries(
        self,
        credential: MailCredential,
        folder: str,
        criteria: dict[str, Any],
        *,
        limit: int,
        before_uid: int | None,
    ) -> tuple[list[dict[str, Any]], int | None]:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=True)
            query = self._imap_search_query(criteria)
            status, data = client.uid("search", None, query)
            if status != "OK" or not data or not data[0]:
                return [], None
            uids = [int(x) for x in data[0].split() if x.isdigit()]
            uids.sort(reverse=True)
            if before_uid is not None:
                uids = [u for u in uids if u < before_uid]
            page = uids[: limit + 1]
            returned = page[:limit]
            next_before = returned[-1] if len(page) > limit else None
            summaries = [self._fetch_summary(client, uid) for uid in returned]
            return summaries, next_before

    def fetch_message(
        self,
        credential: MailCredential,
        folder: str,
        uid: int,
        *,
        max_bytes: int,
    ) -> dict[str, Any]:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=True)
            status, data = client.uid(
                "fetch",
                str(uid),
                "(BODY.PEEK[] FLAGS RFC822.SIZE)",
            )
            if status != "OK" or not data:
                raise MailAdapterError("uid_not_found", "Mail message UID does not exist.")
            raw = self._extract_fetch_body(data)
            if raw is None:
                raise MailAdapterError("uid_not_found", "Mail message UID does not exist.")
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
                truncated = True
            else:
                truncated = False
            msg = email.message_from_bytes(raw)
            summary = self._summary_from_message(msg, uid)
            text, html = self._extract_text_html(msg, max_bytes)
            return {
                "summary": summary,
                "references": self._references(msg),
                "cc": _addresses_from_header(msg, "Cc"),
                "reply_to": _addresses_from_header(msg, "Reply-To"),
                "text": text,
                "html": html,
                "attachments": self._attachment_metadata(msg),
                "truncated": truncated,
            }

    def download_attachment(
        self,
        credential: MailCredential,
        folder: str,
        uid: int,
        attachment_id: str,
    ) -> dict[str, Any]:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=True)
            part = attachment_id
            status, data = client.uid("fetch", str(uid), f"(BODY.PEEK[{part}])")
            if status != "OK" or not data:
                raise MailAdapterError("uid_not_found", "Attachment not found.")
            raw = self._extract_fetch_body(data)
            if raw is None:
                raise MailAdapterError("uid_not_found", "Attachment not found.")
            if len(raw) > MAIL_ATTACHMENT_BYTE_LIMIT:
                raise MailAdapterError("size_limit", "Attachment exceeds download size limit.")
            return {
                "attachment_id": attachment_id,
                "content_base64": base64.b64encode(raw).decode("ascii"),
                "size": len(raw),
            }

    def mark_seen(self, credential: MailCredential, folder: str, uid: int) -> None:
        self._set_flag(credential, folder, uid, "\\Seen", add=True)

    def mark_unseen(self, credential: MailCredential, folder: str, uid: int) -> None:
        self._set_flag(credential, folder, uid, "\\Seen", add=False)

    def move_message(
        self, credential: MailCredential, folder: str, uid: int, target_folder: str
    ) -> None:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=False)
            status, _ = client.uid("copy", str(uid), target_folder)
            if status != "OK":
                raise MailAdapterError("folder_not_found", "Mail folder does not exist.")
            client.uid("store", str(uid), "+FLAGS", "(\\Deleted)")
            client.expunge()

    def delete_message(self, credential: MailCredential, folder: str, uid: int) -> None:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=False)
            status, _ = client.uid("store", str(uid), "+FLAGS", "(\\Deleted)")
            if status != "OK":
                raise MailAdapterError("uid_not_found", "Mail message UID does not exist.")
            client.expunge()

    def get_folder_status(self, credential: MailCredential, folder: str) -> dict[str, Any]:
        with self._imap(credential) as client:
            status, data = client.status(
                folder,
                "(MESSAGES RECENT UNSEEN UIDNEXT UIDVALIDITY)",
            )
            if status != "OK" or not data:
                raise MailAdapterError("folder_not_found", "Mail folder does not exist.")
            parsed = self._parse_status_response(data[0])
            return {"folder": folder, **parsed}

    def send_mail(self, credential: MailCredential, message: EmailMessage) -> dict[str, Any]:
        with self._smtp(credential) as smtp:
            refused = smtp.send_message(message)
            accepted = [message["To"]] if message.get("To") else []
            return {
                "message_id": message.get("Message-ID"),
                "accepted": accepted,
                "rejected": list(refused.keys()) if isinstance(refused, dict) else [],
                "response": "ok",
            }

    @contextmanager
    def _imap(self, credential: MailCredential) -> Iterator[imaplib.IMAP4_SSL]:
        client = imaplib.IMAP4_SSL(
            credential.imap_host,
            MAIL_IMAP_PORT,
            timeout=MAIL_CONNECTION_TIMEOUT_SEC,
        )
        try:
            client.login(credential.email, credential.authorization_code)
            yield client
        finally:
            try:
                client.logout()
            except Exception:
                try:
                    client.shutdown()
                except Exception:
                    pass

    @contextmanager
    def _smtp(self, credential: MailCredential) -> Iterator[smtplib.SMTP_SSL]:
        smtp = smtplib.SMTP_SSL(
            credential.smtp_host,
            credential.smtp_port,
            timeout=MAIL_CONNECTION_TIMEOUT_SEC,
            context=ssl.create_default_context(),
        )
        try:
            smtp.login(credential.email, credential.authorization_code)
            yield smtp
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

    @staticmethod
    def _select_mailbox(
        client: imaplib.IMAP4_SSL, folder: str, *, readonly: bool
    ) -> None:
        status, _ = client.select(f'"{folder}"' if " " in folder else folder, readonly=readonly)
        if status != "OK":
            raise MailAdapterError("folder_not_found", "Mail folder does not exist.")

    @staticmethod
    def _imap_search_query(criteria: dict[str, Any]) -> str:
        parts: list[str] = []
        if criteria.get("unseen"):
            parts.append("UNSEEN")
        if criteria.get("from"):
            parts.append(f'FROM "{criteria["from"]}"')
        if criteria.get("to"):
            parts.append(f'TO "{criteria["to"]}"')
        if criteria.get("subject"):
            parts.append(f'SUBJECT "{criteria["subject"]}"')
        if criteria.get("text"):
            parts.append(f'TEXT "{criteria["text"]}"')
        if criteria.get("since"):
            parts.append(f'SINCE {criteria["since"]}')
        if criteria.get("before"):
            parts.append(f'BEFORE {criteria["before"]}')
        return " ".join(parts) if parts else "ALL"

    def _fetch_summary(self, client: imaplib.IMAP4_SSL, uid: int) -> dict[str, Any]:
        status, data = client.uid(
            "fetch",
            str(uid),
            "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] RFC822.SIZE)",
        )
        if status != "OK" or not data:
            raise MailAdapterError("uid_not_found", "Mail message UID does not exist.")
        raw = self._extract_fetch_body(data, header_only=True)
        flags = self._extract_flags(data)
        msg = email.message_from_bytes(raw or b"")
        summary = self._summary_from_message(msg, uid)
        summary["flags"] = flags
        summary["seen"] = "\\Seen" in flags
        return summary

    @staticmethod
    def _summary_from_message(msg: email.message.Message, uid: int) -> dict[str, Any]:
        date_hdr = msg.get("Date")
        date_val: str | None = None
        if date_hdr:
            try:
                date_val = parsedate_to_datetime(date_hdr).isoformat()
            except (TypeError, ValueError, OverflowError):
                date_val = str(date_hdr)
        from_hdr = msg.get("From")
        return {
            "uid": uid,
            "messageId": msg.get("Message-ID"),
            "subject": _decode_mime_header(msg.get("Subject")),
            "from": _address_dict(from_hdr),
            "to": _addresses_from_header(msg, "To"),
            "date": date_val,
            "flags": [],
            "seen": False,
            "hasAttachments": any(
                p.get_content_disposition() == "attachment"
                for p in msg.walk()
                if not p.is_multipart()
            ),
            "size": None,
        }

    @staticmethod
    def _extract_fetch_body(data: list[Any], *, header_only: bool = False) -> bytes | None:
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                payload = item[1]
                if header_only and b"\r\n\r\n" in payload:
                    return payload
                if not header_only:
                    marker = b"\r\n\r\n"
                    idx = payload.find(marker)
                    return payload[idx + 4 :] if idx >= 0 else payload
        return None

    @staticmethod
    def _extract_flags(data: list[Any]) -> list[str]:
        for item in data:
            if isinstance(item, bytes):
                text = item.decode("utf-8", errors="replace")
                match = re.search(r"FLAGS \(([^)]*)\)", text)
                if match:
                    return [f.strip() for f in match.group(1).split() if f.strip()]
        return []

    @staticmethod
    def _extract_text_html(
        msg: email.message.Message, max_bytes: int
    ) -> tuple[str | None, str | None]:
        text: str | None = None
        html: str | None = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    continue
                ctype = part.get_content_type()
                try:
                    payload = part.get_payload(decode=True) or b""
                except (TypeError, ValueError):
                    continue
                if len(payload) > max_bytes:
                    payload = payload[:max_bytes]
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if ctype == "text/plain" and text is None:
                    text = decoded
                elif ctype == "text/html" and html is None:
                    html = decoded
        else:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html = decoded
            else:
                text = decoded
        return text, html

    @staticmethod
    def _attachment_metadata(msg: email.message.Message) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        index = 1
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue
            filename = part.get_filename()
            items.append(
                {
                    "attachmentId": str(index),
                    "filename": _decode_mime_header(filename),
                    "contentType": part.get_content_type(),
                    "size": len(part.get_payload(decode=True) or b""),
                    "contentId": part.get("Content-ID"),
                }
            )
            index += 1
        return items

    @staticmethod
    def _references(msg: email.message.Message) -> list[str]:
        refs: list[str] = []
        for key in ("References", "In-Reply-To"):
            raw = msg.get(key)
            if not raw:
                continue
            refs.extend(re.findall(r"<[^>]+>", str(raw)))
        return refs

    def _set_flag(
        self,
        credential: MailCredential,
        folder: str,
        uid: int,
        flag: str,
        *,
        add: bool,
    ) -> None:
        with self._imap(credential) as client:
            self._select_mailbox(client, folder, readonly=False)
            op = "+FLAGS" if add else "-FLAGS"
            status, _ = client.uid("store", str(uid), op, f"({flag})")
            if status != "OK":
                raise MailAdapterError("uid_not_found", "Mail message UID does not exist.")

    @staticmethod
    def _parse_status_response(line: bytes | str) -> dict[str, Any]:
        text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
        def _int(key: str) -> int | None:
            match = re.search(rf"{key}\s+(\d+)", text, re.IGNORECASE)
            return int(match.group(1)) if match else None

        return {
            "messages": _int("MESSAGES"),
            "recent": _int("RECENT"),
            "unseen": _int("UNSEEN"),
            "uidNext": _int("UIDNEXT"),
            "uidValidity": _int("UIDVALIDITY"),
        }


def build_outgoing_message(
    credential: MailCredential,
    *,
    to: list[str],
    subject: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    text: str | None = None,
    html: str | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = credential.email
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg["Subject"] = subject
    if html and text:
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
    elif html:
        msg.set_content(html, subtype="html")
    elif text:
        msg.set_content(text)
    else:
        msg.set_content("")
    return msg
