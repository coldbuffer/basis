"""Workspace connector OAuth authorize-url and exchange over HTTP."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from basis.services.connector.vault.connector_oauth_state import (
    pack_connector_oauth_state,
    unpack_connector_oauth_state,
)
from basis.infra.runtime.config import Settings
from basis.infra.e2e_sandbox.playwright_oauth_stub import PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX
from basis.app import create_app

_REDIRECT_URI = "http://localhost/connectors/oauth/callback"
_CODE_VERIFIER = "integration-pkce-verifier-0123456789"
# S256 of _CODE_VERIFIER (precomputed for stable assertions).
_CODE_CHALLENGE = "4nCyRkh2nJauiTKPmjiK9JIgrlqDIRN0ocRU34IAlgA"


def _e2e_data_dir(tmp_path: Path) -> Path:
    """Use Playwright data-dir gating so token exchange uses the in-process OAuth stub."""
    return tmp_path / "data" / "e2e"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=_e2e_data_dir(tmp_path))))


def _session_headers(client: TestClient, email: str = "oauth-http@basis.local") -> tuple[dict[str, str], str]:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "OAuth HTTP"},
    )
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return headers, workspace_id


def _put_github_oauth_config(client: TestClient, workspace_id: str, headers: dict[str, str]) -> None:
    base = f"/api/v1/workspaces/{workspace_id}/connectors/oauth-configs/github"
    put = client.put(
        base,
        headers=headers,
        json={
            "client_id": "gh_integration_client",
            "client_secret": "gh_integration_secret",
            "redirect_uri": _REDIRECT_URI,
        },
    )
    assert put.status_code == 200, put.text


def _enable_github(client: TestClient, workspace_id: str, headers: dict[str, str]) -> None:
    narrow = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres", "github"], "action_policy": {}},
    )
    assert narrow.status_code == 200, narrow.text


def test_authorize_url_requires_oauth_config(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _enable_github(client, workspace_id, headers)

    url_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/authorize-url"
    missing = client.post(
        url_route,
        headers=headers,
        json={"code_challenge": _CODE_CHALLENGE, "redirect_uri": _REDIRECT_URI},
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "oauth_authorize_url_failed"


def test_authorize_url_requires_pkce_for_github(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _enable_github(client, workspace_id, headers)
    _put_github_oauth_config(client, workspace_id, headers)

    url_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/authorize-url"
    no_pkce = client.post(url_route, headers=headers, json={"redirect_uri": _REDIRECT_URI})
    assert no_pkce.status_code == 422
    assert no_pkce.json()["detail"]["code"] == "oauth_authorize_url_failed"


def test_authorize_url_includes_pkce_query_params(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _enable_github(client, workspace_id, headers)
    _put_github_oauth_config(client, workspace_id, headers)

    url_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/authorize-url"
    built = client.post(
        url_route,
        headers=headers,
        json={
            "state": "integration-oauth-state",
            "redirect_uri": _REDIRECT_URI,
            "code_challenge": _CODE_CHALLENGE,
        },
    )
    assert built.status_code == 200, built.text
    body = built.json()
    assert body["state"] == "integration-oauth-state"
    parsed = urlparse(body["authorize_url"])
    qs = parse_qs(parsed.query)
    assert qs["code_challenge"] == [_CODE_CHALLENGE]
    assert qs["code_challenge_method"] == ["S256"]
    assert qs["state"] == ["integration-oauth-state"]
    assert qs["client_id"] == ["gh_integration_client"]


def test_exchange_stub_persists_workspace_connection(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _enable_github(client, workspace_id, headers)
    _put_github_oauth_config(client, workspace_id, headers)

    stub_code = f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}integration"
    exchange_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/exchange"
    exchanged = client.post(
        exchange_route,
        headers=headers,
        json={
            "code": stub_code,
            "redirect_uri": _REDIRECT_URI,
            "code_verifier": _CODE_VERIFIER,
            "connection_scope": "workspace",
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    conn = exchanged.json()["connection"]
    assert conn["service"] == "github"
    assert conn["connection_scope"] == "workspace"
    assert conn.get("subject_id") in ("", None)

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections",
        headers=headers,
        params={"service": "github"},
    )
    assert listed.status_code == 200
    services = {c["service"] for c in listed.json()["connections"]}
    assert "github" in services


def test_oauth_state_pack_unpack_roundtrip() -> None:
    state = pack_connector_oauth_state("github", "user-42")
    assert unpack_connector_oauth_state(state) == {"service": "github", "subject_id": "user-42"}


def test_exchange_rejects_when_github_not_in_workspace_policy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _put_github_oauth_config(client, workspace_id, headers)

    narrow = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres"], "action_policy": {}},
    )
    assert narrow.status_code == 200

    stub_code = f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}policy-block"
    exchange_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/exchange"
    denied = client.post(
        exchange_route,
        headers=headers,
        json={
            "code": stub_code,
            "redirect_uri": _REDIRECT_URI,
            "code_verifier": _CODE_VERIFIER,
        },
    )
    assert denied.status_code == 422
    assert denied.json()["detail"]["code"] == "oauth_exchange_failed"


def test_authorize_url_rejects_when_github_not_in_workspace_policy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)
    _put_github_oauth_config(client, workspace_id, headers)

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres"], "action_policy": {}},
    )

    url_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/authorize-url"
    denied = client.post(
        url_route,
        headers=headers,
        json={"code_challenge": _CODE_CHALLENGE, "redirect_uri": _REDIRECT_URI},
    )
    assert denied.status_code == 422
    assert denied.json()["detail"]["code"] == "oauth_authorize_url_failed"


def test_manifest_route_blocked_when_github_not_in_workspace_policy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers, workspace_id = _session_headers(client)

    narrow = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres"], "action_policy": {}},
    )
    assert narrow.status_code == 200

    denied = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog/github",
        headers=headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "connector_policy_blocked"


def test_viewer_cannot_authorize_or_exchange(tmp_path: Path) -> None:
    client = _client(tmp_path)
    owner_headers, workspace_id = _session_headers(client, "oauth-owner@basis.local")
    _enable_github(client, workspace_id, owner_headers)
    _put_github_oauth_config(client, workspace_id, owner_headers)

    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": "oauth-viewer@basis.local", "password": "password123", "display_name": "Viewer"},
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": viewer["user"]["id"], "role": "viewer"},
    )
    viewer_headers = {"Authorization": f"Bearer {viewer['token']}"}

    authorize_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/authorize-url"
    assert (
        client.post(
            authorize_route,
            headers=viewer_headers,
            json={"code_challenge": _CODE_CHALLENGE, "redirect_uri": _REDIRECT_URI},
        ).status_code
        == 403
    )

    exchange_route = f"/api/v1/workspaces/{workspace_id}/connectors/oauth/github/exchange"
    assert (
        client.post(
            exchange_route,
            headers=viewer_headers,
            json={"code": f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}x", "code_verifier": _CODE_VERIFIER},
        ).status_code
        == 403
    )
