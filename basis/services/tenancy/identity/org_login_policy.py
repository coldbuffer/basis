"""Organization auth policy values stored on ``organizations.auth_policy``."""

from __future__ import annotations

ORG_AUTH_POLICIES = frozenset({"password_allowed", "sso_preferred", "sso_required"})
