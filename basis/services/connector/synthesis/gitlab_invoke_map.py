"""GitLab REST v4 path hints for AnyConnect ``gitlab.*`` action ids."""

from __future__ import annotations

_GITLAB_BY_SUFFIX: dict[str, tuple[str, str]] = {
    "list_projects": ("GET", "/api/v4/projects"),
    "get_project": ("GET", "/api/v4/projects/{{projectId}}"),
    "create_project": ("POST", "/api/v4/projects"),
    "update_project": ("PUT", "/api/v4/projects/{{projectId}}"),
    "delete_project": ("DELETE", "/api/v4/projects/{{projectId}}"),
    "list_project_issues": ("GET", "/api/v4/projects/{{projectId}}/issues"),
    "get_project_issue": ("GET", "/api/v4/projects/{{projectId}}/issues/{{issueIid}}"),
    "create_project_issue": ("POST", "/api/v4/projects/{{projectId}}/issues"),
    "update_project_issue": ("PUT", "/api/v4/projects/{{projectId}}/issues/{{issueIid}}"),
    "delete_project_issue": ("DELETE", "/api/v4/projects/{{projectId}}/issues/{{issueIid}}"),
    "list_project_merge_requests": (
        "GET",
        "/api/v4/projects/{{projectId}}/merge_requests",
    ),
    "create_merge_request": ("POST", "/api/v4/projects/{{projectId}}/merge_requests"),
    "merge_merge_request": (
        "PUT",
        "/api/v4/projects/{{projectId}}/merge_requests/{{mergeRequestIid}}/merge",
    ),
    "update_merge_request": (
        "PUT",
        "/api/v4/projects/{{projectId}}/merge_requests/{{mergeRequestIid}}",
    ),
    "get_current_user": ("GET", "/api/v4/user"),
}


def gitlab_invoke_wire(action_id: str) -> dict[str, str] | None:
    suffix = action_id.split(".")[-1] if "." in action_id else action_id
    pair = _GITLAB_BY_SUFFIX.get(suffix)
    if not pair:
        return None
    return {"method": pair[0], "path": pair[1]}
