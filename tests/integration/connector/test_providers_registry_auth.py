"""Upstream providers registry auth_mode → BOCP mapping."""

from __future__ import annotations

import pytest

from basis.services.connector.synthesis.auth_mode_reference import (
    ALL_AUTH_MODES,
    REGISTRY_CANONICAL_BY_AUTH_MODE,
    REGISTRY_MODES_WITHOUT_BOCP_ENUM,
)
from basis.services.connector.synthesis.providers_registry_auth import registry_auth_mode_to_bocp


def test_registry_auth_mode_to_bocp_mapping() -> None:
    assert registry_auth_mode_to_bocp("OAUTH2") == "oauth2"
    assert registry_auth_mode_to_bocp("MCP_OAUTH2") == "oauth2"
    assert registry_auth_mode_to_bocp("OAUTH2_CC") == "oauth2_cc"
    assert registry_auth_mode_to_bocp("BILL") == "custom"
    assert registry_auth_mode_to_bocp("UNKNOWN_X") == "custom"


@pytest.mark.parametrize("registry_extra", sorted(REGISTRY_MODES_WITHOUT_BOCP_ENUM))
def test_registry_extra_modes_map_to_bocp(registry_extra: str) -> None:
    bocp = registry_auth_mode_to_bocp(registry_extra)
    assert bocp in ("oauth2", "custom")


def test_all_bocp_modes_documented_in_reference() -> None:
    documented = set(REGISTRY_CANONICAL_BY_AUTH_MODE) | {"database_dsn"}
    assert documented == ALL_AUTH_MODES
