"""OAuth state payload for end_user connector flows (service + subject_id)."""

from __future__ import annotations

import base64
import json
import uuid


def pack_connector_oauth_state(service: str, subject_id: str) -> str:
    payload = {
        "v": 1,
        "service": service,
        "subject_id": subject_id,
        "n": uuid.uuid4().hex[:12],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def unpack_connector_oauth_state(state: str) -> dict[str, str]:
    try:
        raw = base64.urlsafe_b64decode(state.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid OAuth state") from exc
    if not isinstance(parsed, dict) or parsed.get("v") != 1:
        raise ValueError("Invalid OAuth state version")
    service = str(parsed.get("service") or "").strip()
    subject_id = str(parsed.get("subject_id") or "").strip()
    if not service or not subject_id:
        raise ValueError("OAuth state missing service or subject_id")
    return {"service": service, "subject_id": subject_id}
