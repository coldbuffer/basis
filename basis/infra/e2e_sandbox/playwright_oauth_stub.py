"""OAuth token exchange stub for Playwright E2E (data/e2e only)."""

from __future__ import annotations

import httpx

PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX = "e2e_playwright_oauth_"


def playwright_e2e_oauth_http_client(code: str) -> httpx.Client | None:
    """Return a mock HTTP client when `code` is the Playwright stub authorization code."""
    if not code.startswith(PLAYWRIGHT_E2E_OAUTH_CODE_PREFIX):
        return None

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": f"gho_stub_{code}",
                "token_type": "bearer",
                "scope": "read:user",
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))
