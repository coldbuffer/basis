"""Slack Web API path hints for AnyConnect action ids (until full TS extractor)."""

from __future__ import annotations

# Suffix after ``slack.`` → (method, path)
_SLACK_INVOKE_BY_SUFFIX: dict[str, tuple[str, str]] = {
    "add_reaction": ("POST", "/reactions.add"),
    "remove_reaction": ("POST", "/reactions.remove"),
    "delete_message": ("POST", "/chat.delete"),
    "delete_file": ("POST", "/files.delete"),
    "get_channel_messages": ("GET", "/conversations.history"),
    "get_conversation": ("GET", "/conversations.info"),
    "get_file": ("GET", "/files.info"),
    "get_message_permalink": ("GET", "/chat.getPermalink"),
    "get_reactions": ("GET", "/reactions.get"),
    "get_thread": ("GET", "/conversations.replies"),
    "get_user": ("GET", "/users.info"),
    "list_channels": ("GET", "/conversations.list"),
    "list_conversations": ("GET", "/conversations.list"),
    "list_files": ("GET", "/files.list"),
    "list_users": ("GET", "/users.list"),
    "open_conversation": ("POST", "/conversations.open"),
    "post_ephemeral_message": ("POST", "/chat.postEphemeral"),
    "post_message": ("POST", "/chat.postMessage"),
    "reply_message": ("POST", "/chat.postMessage"),
    "schedule_message": ("POST", "/chat.scheduleMessage"),
    "search_messages": ("GET", "/search.messages"),
    "update_message": ("POST", "/chat.update"),
    "upload_file": ("POST", "/files.upload"),
}


def slack_invoke_wire(action_id: str) -> dict[str, str] | None:
    suffix = action_id.split(".")[-1] if "." in action_id else action_id
    pair = _SLACK_INVOKE_BY_SUFFIX.get(suffix)
    if not pair:
        return None
    return {"method": pair[0], "path": pair[1]}
