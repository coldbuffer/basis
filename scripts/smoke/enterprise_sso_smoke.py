#!/usr/bin/env python3
"""Public SSO endpoint smoke checks (F-ACC-07). No credentials required."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read(512).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(512).decode("utf-8", errors="replace")
        return exc.code, body


def main() -> int:
    base = os.environ.get("BASIS_PUBLIC_URL", "http://localhost:8090").rstrip("/")
    failures: list[str] = []

    status, _ = _get(f"{base}/api/v1/auth/org-sso-options")
    if status != 200:
        failures.append(f"org-sso-options expected 200, got {status}")

    status, _ = _get(f"{base}/api/v1/auth/org-sso-hint?email=smoke@example.com")
    if status not in (200, 404):
        failures.append(f"org-sso-hint expected 200 or 404, got {status}")

    status, _ = _get(f"{base}/api/v1/auth/saml/__smoke__/metadata")
    if status not in (404, 503):
        failures.append(f"saml metadata for unknown org expected 404 or 503, got {status}")

    if failures:
        for line in failures:
            print(f"FAIL: {line}", file=sys.stderr)
        return 1

    print(f"OK: enterprise SSO smoke passed against {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
