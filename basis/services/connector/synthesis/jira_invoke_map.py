"""Jira Cloud (Atlassian) path hints for AnyConnect ``jira.*`` action ids."""

from __future__ import annotations

# ``cloudId`` lives in workspace ``connection_config`` (post-connection setup).
_JIRA_BY_SUFFIX: dict[str, tuple[str, str]] = {
    "list_projects": ("GET", "/ex/jira/{{config.cloudId}}/rest/api/3/project"),
    "get_project": (
        "GET",
        "/ex/jira/{{config.cloudId}}/rest/api/3/project/{{projectIdOrKey}}",
    ),
    "search_issues": ("POST", "/ex/jira/{{config.cloudId}}/rest/api/3/search"),
    "get_issue": (
        "GET",
        "/ex/jira/{{config.cloudId}}/rest/api/3/issue/{{issueIdOrKey}}",
    ),
    "create_issue": ("POST", "/ex/jira/{{config.cloudId}}/rest/api/3/issue"),
    "list_issue_comments": (
        "GET",
        "/ex/jira/{{config.cloudId}}/rest/api/3/issue/{{issueIdOrKey}}/comment",
    ),
    "add_comment": (
        "POST",
        "/ex/jira/{{config.cloudId}}/rest/api/3/issue/{{issueIdOrKey}}/comment",
    ),
}


def jira_invoke_wire(action_id: str) -> dict[str, str] | None:
    suffix = action_id.split(".")[-1] if "." in action_id else action_id
    pair = _JIRA_BY_SUFFIX.get(suffix)
    if not pair:
        return None
    return {"method": pair[0], "path": pair[1]}
