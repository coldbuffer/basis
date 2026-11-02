"""Shipped provider auth blocks: display names and known real-provider coverage."""

from __future__ import annotations

from basis.services.connector.catalog import ConnectorCatalog


_REAL_AUTH_MODE_COVERAGE: dict[str, frozenset[str]] = {
    "oauth2": frozenset({"github"}),
    "api_key": frozenset({"github"}),
    "database_dsn": frozenset({"postgres", "mysql"}),
    "custom": frozenset({"qq_mail"}),
}


def test_shipped_provider_auth_entries_have_display_name() -> None:
    catalog = ConnectorCatalog.load_from_directory()
    for manifest in catalog.list_manifests():
        for auth in manifest.auth:
            assert auth.display_name, (
                f"{manifest.service} auth_mode {auth.auth_mode} missing display_name"
            )


def test_real_provider_auth_mode_coverage_documented() -> None:
    """Shipped providers: postgres, mysql, github, qq_mail."""
    catalog = ConnectorCatalog.load_from_directory()
    assert {m.service for m in catalog.list_manifests()} == {
        "github",
        "mysql",
        "postgres",
        "qq_mail",
    }

    by_mode: dict[str, set[str]] = {}
    for manifest in catalog.list_manifests():
        for auth in manifest.auth:
            by_mode.setdefault(auth.auth_mode, set()).add(manifest.service)

    for mode, expected_services in _REAL_AUTH_MODE_COVERAGE.items():
        assert by_mode.get(mode, set()) >= expected_services
