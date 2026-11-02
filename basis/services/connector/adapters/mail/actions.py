"""OpenConnector-aligned mail action dispatch."""

from __future__ import annotations

from typing import Any

from basis.services.connector.adapters.mail.credentials import (
    MailCredential,
    read_mail_credential,
)
from basis.services.connector.adapters.mail.errors import MailAdapterError
from basis.services.connector.adapters.mail.protocol import (
    MAIL_MESSAGE_FETCH_BYTE_LIMIT,
    ImapSmtpProtocol,
    build_outgoing_message,
)

DEFAULT_FOLDER = "INBOX"
DEFAULT_LIMIT = 20

_MAIL_ACTIONS = frozenset(
    {
        "send_email",
        "list_folders",
        "search_emails",
        "get_email",
        "download_attachment",
        "mark_email_read",
        "mark_email_unread",
        "move_email",
        "delete_email",
        "get_folder_status",
        "reply_email",
        "forward_email",
    }
)


def is_mail_action(name: str) -> bool:
    return name in _MAIL_ACTIONS


def execute_mail_action(
    service: str,
    action_name: str,
    credentials: dict[str, Any],
    arguments: dict[str, Any] | None,
    *,
    protocol: ImapSmtpProtocol | None = None,
) -> Any:
    if action_name not in _MAIL_ACTIONS:
        raise MailAdapterError("unsupported", f"Unsupported mail action: {action_name}")
    cred = read_mail_credential(service, credentials)
    proto = protocol or ImapSmtpProtocol()
    args = dict(arguments or {})

    if action_name == "list_folders":
        folders = proto.list_folders(cred)
        return {
            "folders": [
                {
                    "path": f.path,
                    "name": f.name,
                    "delimiter": f.delimiter,
                    "flags": f.flags,
                    "specialUse": f.special_use,
                }
                for f in folders
            ]
        }

    if action_name == "search_emails":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        limit = int(args.get("limit") or DEFAULT_LIMIT)
        before_uid = args.get("beforeUid")
        if before_uid is not None:
            before_uid = int(before_uid)
        criteria = {
            k: args[k]
            for k in ("unseen", "from", "to", "subject", "text", "since", "before")
            if k in args and args[k] is not None
        }
        summaries, next_before = proto.search_summaries(
            cred,
            folder,
            criteria,
            limit=min(max(1, limit), 100),
            before_uid=before_uid,
        )
        return {
            "folder": folder,
            "emails": summaries,
            "nextBeforeUid": next_before,
        }

    if action_name == "get_email":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        message = proto.fetch_message(
            cred, folder, uid, max_bytes=MAIL_MESSAGE_FETCH_BYTE_LIMIT
        )
        summary = message["summary"]
        return {
            "folder": folder,
            "uid": summary["uid"],
            "messageId": summary.get("messageId"),
            "subject": summary.get("subject"),
            "from": summary.get("from"),
            "to": summary.get("to"),
            "cc": message.get("cc"),
            "date": summary.get("date"),
            "flags": summary.get("flags"),
            "seen": summary.get("seen"),
            "text": message.get("text"),
            "html": message.get("html"),
            "truncated": message.get("truncated"),
            "attachments": message.get("attachments"),
        }

    if action_name == "download_attachment":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        attachment_id = str(args["attachmentId"])
        blob = proto.download_attachment(cred, folder, uid, attachment_id)
        return {
            "folder": folder,
            "uid": uid,
            "attachmentId": attachment_id,
            "size": blob.get("size"),
            "contentBase64": blob.get("content_base64"),
        }

    if action_name == "mark_email_read":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        proto.mark_seen(cred, folder, uid)
        return {"folder": folder, "uid": uid, "read": True}

    if action_name == "mark_email_unread":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        proto.mark_unseen(cred, folder, uid)
        return {"folder": folder, "uid": uid, "read": False}

    if action_name == "move_email":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        target = str(args["targetFolder"])
        proto.move_message(cred, folder, uid, target)
        return {"folder": folder, "uid": uid, "targetFolder": target, "moved": True}

    if action_name == "delete_email":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        proto.delete_message(cred, folder, uid)
        return {"folder": folder, "uid": uid, "deleted": True}

    if action_name == "get_folder_status":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        return proto.get_folder_status(cred, folder)

    if action_name == "send_email":
        msg = build_outgoing_message(
            cred,
            to=list(args["to"]),
            subject=str(args["subject"]),
            cc=list(args.get("cc") or []) or None,
            bcc=list(args.get("bcc") or []) or None,
            reply_to=args.get("replyTo"),
            text=args.get("text"),
            html=args.get("html"),
        )
        return proto.send_mail(cred, msg)

    if action_name == "reply_email":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        original = proto.fetch_message(
            cred, folder, uid, max_bytes=MAIL_MESSAGE_FETCH_BYTE_LIMIT
        )
        summary = original["summary"]
        reply_all = bool(args.get("replyAll", False))
        to_addrs = list(args.get("to") or [])
        if not to_addrs:
            from_addr = (summary.get("from") or {}).get("email")
            if from_addr:
                to_addrs = [from_addr]
        cc_addrs = list(args.get("cc") or [])
        if reply_all:
            for addr in summary.get("to") or []:
                email_addr = addr.get("email")
                if email_addr and email_addr != cred.email:
                    cc_addrs.append(email_addr)
        subject = str(args.get("subject") or f"Re: {summary.get('subject') or ''}")
        refs = " ".join(original.get("references") or [])
        in_reply = summary.get("messageId")
        msg = build_outgoing_message(
            cred,
            to=to_addrs,
            subject=subject,
            cc=cc_addrs or None,
            bcc=list(args.get("bcc") or []) or None,
            in_reply_to=in_reply,
            references=refs or in_reply,
            text=args.get("text"),
            html=args.get("html"),
        )
        return proto.send_mail(cred, msg)

    if action_name == "forward_email":
        folder = str(args.get("folder") or DEFAULT_FOLDER)
        uid = int(args["uid"])
        original = proto.fetch_message(
            cred, folder, uid, max_bytes=MAIL_MESSAGE_FETCH_BYTE_LIMIT
        )
        summary = original["summary"]
        subject = str(args.get("subject") or f"Fwd: {summary.get('subject') or ''}")
        body_text = args.get("text")
        if body_text is None and original.get("text"):
            body_text = f"\n\n---------- Forwarded message ----------\n{original.get('text')}"
        msg = build_outgoing_message(
            cred,
            to=list(args["to"]),
            subject=subject,
            cc=list(args.get("cc") or []) or None,
            bcc=list(args.get("bcc") or []) or None,
            text=body_text,
            html=args.get("html"),
        )
        return proto.send_mail(cred, msg)

    raise MailAdapterError("unsupported", f"Unsupported mail action: {action_name}")
