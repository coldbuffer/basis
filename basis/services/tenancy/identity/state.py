"""Signed OAuth state payloads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any


def sign_oauth_state(secret: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    raw = f"{body}.{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_oauth_state(secret: str, token: str) -> dict[str, Any]:
    pad = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode((token + pad).encode()).decode()
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid state") from exc
    if "." not in decoded:
        raise ValueError("invalid state")
    body, sig = decoded.rsplit(".", 1)
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("invalid state signature")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("invalid state payload")
    return data


def new_nonce() -> str:
    return secrets.token_urlsafe(16)
