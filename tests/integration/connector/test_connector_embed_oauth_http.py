"""Embed connector OAuth authorize-url and exchange (end_user scope)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from basis.services.connector.vault.connector_oauth_state import unpack_connector_oauth_state
from basis.infra.runtime.config import Settings
from basis.infra.e2e_sandbox.playwright_oauth_stub import PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX
from basis.app import create_app

_REDIRECT_URI = "http://localhost/embed/oauth/callback"
_CODE_VERIFIER = "integration-pkce-verifier-0123456789"
_CODE_CHALLENGE = "4nCyRkh2nJauiTKPmjiK9JIgrlqDIRN0ocRU34IAlgA"
_SUBJECT_ID = "fellow-user-embed-oauth-1"


def _client(tmp_path: Path, *, e2e_data_dir: bool = False) -> TestClient:
    data_dir = tmp_path / "data" / "e2e" if e2e_data_dir else tmp_path / "basis_data"
    return TestClient(create_app(Settings(data_dir=data_dir)))


def _session(tmp_path: Path, *, e2e_data_dir: bool = False) -> tuple[TestClient, str, dict[str, str]]:
    client = _client(tmp_path, e2e_data_dir=e2e_data_dir)
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "embed-oauth@basis.local", "password": "password123", "display_name": "Embed"},
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, workspace_id, headers


def _enable_github_and_oauth_config(
    client: TestClient, workspace_id: str, headers: dict[str, str]
) -> None:
    policy = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["github"], "action_policy": {}},
    )
    assert policy.status_code == 200
    oauth = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/oauth-configs/github",
        headers=headers,
        json={
            "client_id": "gh_embed_client",
            "client_secret": "gh_embed_secret",
            "redirect_uri": _REDIRECT_URI,
        },
    )
    assert oauth.status_code == 200


def test_embed_authorize_url_binds_subject_in_state(tmp_path: Path) -> None:
    client, workspace_id, headers = _session(tmp_path)
    _enable_github_and_oauth_config(client, workspace_id, headers)

    route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/authorize-url"
    built = client.post(
        route,
        headers=headers,
        json={
            "subject_id": _SUBJECT_ID,
            "redirect_uri": _REDIRECT_URI,
            "code_challenge": _CODE_CHALLENGE,
        },
    )
    assert built.status_code == 200, built.text
    state = built.json()["state"]
    parsed = unpack_connector_oauth_state(state)
    assert parsed == {"service": "github", "subject_id": _SUBJECT_ID}

    qs = parse_qs(urlparse(built.json()["authorize_url"]).query)
    assert qs["state"] == [state]
    assert qs["code_challenge"] == [_CODE_CHALLENGE]


def test_embed_oauth_exchange_requires_end_user_subject(tmp_path: Path) -> None:
    client, workspace_id, headers = _session(tmp_path)
    _enable_github_and_oauth_config(client, workspace_id, headers)

    route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/exchange"
    missing = client.post(
        route,
        headers=headers,
        json={
            "code": "unused-code",
            "connection_scope": "end_user",
            "redirect_uri": _REDIRECT_URI,
        },
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "subject_id_required"


def test_embed_exchange_rejects_when_github_not_in_workspace_policy(tmp_path: Path) -> None:
    client, workspace_id, headers = _session(tmp_path, e2e_data_dir=True)
    _enable_github_and_oauth_config(client, workspace_id, headers)

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres"], "action_policy": {}},
    )

    authorize_route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/authorize-url"
    denied_authorize = client.post(
        authorize_route,
        headers=headers,
        json={
            "subject_id": _SUBJECT_ID,
            "redirect_uri": _REDIRECT_URI,
            "code_challenge": _CODE_CHALLENGE,
        },
    )
    assert denied_authorize.status_code == 422

    exchange_route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/exchange"
    denied_exchange = client.post(
        exchange_route,
        headers=headers,
        json={
            "code": f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}embed-block",
            "subject_id": _SUBJECT_ID,
            "redirect_uri": _REDIRECT_URI,
            "code_verifier": _CODE_VERIFIER,
        },
    )
    assert denied_exchange.status_code == 422
    assert denied_exchange.json()["detail"]["code"] == "oauth_exchange_failed"


def test_embed_oauth_exchange_stub_persists_end_user_connection(tmp_path: Path) -> None:
    client, workspace_id, headers = _session(tmp_path, e2e_data_dir=True)
    _enable_github_and_oauth_config(client, workspace_id, headers)

    authorize_route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/authorize-url"
    built = client.post(
        authorize_route,
        headers=headers,
        json={
            "subject_id": _SUBJECT_ID,
            "redirect_uri": _REDIRECT_URI,
            "code_challenge": _CODE_CHALLENGE,
        },
    )
    assert built.status_code == 200
    state = built.json()["state"]

    stub_code = f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}embed"
    exchange_route = f"/api/v1/workspaces/{workspace_id}/connectors/embed/oauth/github/exchange"
    exchanged = client.post(
        exchange_route,
        headers=headers,
        json={
            "code": stub_code,
            "state": state,
            "redirect_uri": _REDIRECT_URI,
            "code_verifier": _CODE_VERIFIER,
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    conn = exchanged.json()["connection"]
    assert conn["service"] == "github"
    assert conn["connection_scope"] == "end_user"
    assert conn["subject_id"] == _SUBJECT_ID

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/connections",
        headers=headers,
        params={"subject_id": _SUBJECT_ID},
    )
    assert listed.status_code == 200
    assert any(c["service"] == "github" for c in listed.json()["connections"])
