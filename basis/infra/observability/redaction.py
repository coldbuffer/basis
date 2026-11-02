"""Redact secrets and bulky document payloads before logging (X-02)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|passwd|secret|api[_-]?key|token|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|private[_-]?key|bearer)",
    re.IGNORECASE,
)
_BULKY_TEXT_KEY = re.compile(
    r"(^content$|^text$|^body$|document[_-]?content|raw[_-]?text|prompt|completion|"
    r"message[_-]?body|chunk[_-]?text)",
    re.IGNORECASE,
)

_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+\b", re.IGNORECASE)
_BASIC_RE = re.compile(r"\bBasic\s+[A-Za-z0-9+/=]+\b", re.IGNORECASE)
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9]{8,}\b")
_QUERY_SECRET_RE = re.compile(
    r"([?&](?:token|api[_-]?key|access[_-]?token|key)=)[^&\s#]+",
    re.IGNORECASE,
)
_LONG_TEXT_LIMIT = 256


def redact_string(text: str) -> str:
    if not text:
        return text
    out = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    out = _BASIC_RE.sub(f"Basic {REDACTED}", out)
    out = _SK_RE.sub(REDACTED, out)
    out = _QUERY_SECRET_RE.sub(rf"\1{REDACTED}", out)
    return out


def _redact_key_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str) and _BULKY_TEXT_KEY.search(key):
        if len(value) > _LONG_TEXT_LIMIT:
            return f"{REDACTED}({len(value)} chars)"
        return redact_string(value)
    return value


def redact_log_field(key: str, value: Any) -> Any:
    trimmed = _redact_key_value(key, value)
    if trimmed is REDACTED or (
        isinstance(trimmed, str) and trimmed.startswith(REDACTED)
    ):
        return trimmed
    return redact_for_log(trimmed)


def redact_for_log(value: Any) -> Any:
    """Return a JSON-serializable structure safe for log fields."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > _LONG_TEXT_LIMIT:
            return f"{REDACTED}({len(value)} chars)"
        return redact_string(value)
    if isinstance(value, bytes):
        return f"{REDACTED}({len(value)} bytes)"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            trimmed = _redact_key_value(key, v)
            if trimmed is REDACTED or (
                isinstance(trimmed, str) and trimmed.startswith(REDACTED)
            ):
                out[key] = trimmed
            else:
                out[key] = redact_for_log(trimmed)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_for_log(item) for item in value]
    return redact_string(str(value))
