"""Unit/integration: OAuth HTTP client stub used when Playwright exchanges codes."""

from __future__ import annotations

import httpx

from basis.infra.e2e_sandbox.playwright_oauth_stub import (
    PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX,
    playwright_e2e_oauth_http_client,
)


def test_playwright_oauth_stub_client_only_for_prefix() -> None:
    assert playwright_e2e_oauth_http_client("not-a-stub") is None
    client = playwright_e2e_oauth_http_client(f"{PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX}test")
    assert client is not None
    try:
        resp = client.post("https://github.com/login/oauth/access_token", data={"code": "x"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["access_token"].startswith("gho_stub_")
        assert payload["token_type"] == "bearer"
    finally:
        client.close()
