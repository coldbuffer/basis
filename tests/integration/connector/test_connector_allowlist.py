"""Platform + workspace dual-layer BOCP provider allowlists."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app

from basis.services.connector.vault.allowlist import (
    PLATFORM_CONNECTOR_ALLOWLIST_KEY,
    assert_allowed_providers_in_catalog,
    assert_workspace_allowlist_within_platform,
    effective_allowed_providers,
    is_provider_allowed,
    is_workspace_provider_enabled,
    normalize_allowed_providers,
    provider_blocked_layer,
    unknown_catalog_providers,
)
from basis.services.connector import get_connector_catalog
from basis.services.connector.vault.auth_vault import ConnectorAuthVault
from basis.services.connector.vault.platform_policy import (
    get_platform_allowed_providers,
    upsert_platform_allowed_providers,
)
from basis.services.connector.runtime import ConnectorRuntime
from basis.infra.db.sqlite_migrations import run_migrations


def _fresh_db(tmp_path: Path):
    import sqlite3

    db_path = tmp_path / "allowlist.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


def test_is_workspace_provider_enabled() -> None:
    assert is_workspace_provider_enabled("github", "*") is True
    assert is_workspace_provider_enabled("github", ["postgres"]) is False
    assert is_workspace_provider_enabled("postgres", ["postgres"]) is True


def test_normalize_and_effective_allowlist() -> None:
    assert normalize_allowed_providers("postgres, github") == ["github", "postgres"]
    assert effective_allowed_providers("*", "*") == "*"
    assert effective_allowed_providers(["postgres", "github"], "*") == ["github", "postgres"]
    assert effective_allowed_providers(["postgres", "github"], ["postgres"]) == ["postgres"]
    assert effective_allowed_providers(["postgres"], ["postgres", "airtable"]) == ["postgres"]
    assert is_provider_allowed("github", ["postgres"], "*") is False
    assert is_provider_allowed("postgres", ["postgres"], "*") is True
    assert provider_blocked_layer("airtable", ["postgres"], "*") == "platform"


def test_assert_workspace_subset() -> None:
    assert_workspace_allowlist_within_platform("*", ["postgres"])
    assert_workspace_allowlist_within_platform(["postgres"], ["postgres", "github"])
    with pytest.raises(ValueError, match="platform level"):
        assert_workspace_allowlist_within_platform(["airtable"], ["postgres"])


def test_platform_settings_round_trip(tmp_path: Path) -> None:
    conn = _fresh_db(tmp_path)
    try:
        assert get_platform_allowed_providers(conn) == "*"
        upsert_platform_allowed_providers(conn, ["postgres", "github"])
        assert get_platform_allowed_providers(conn) == ["github", "postgres"]
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (PLATFORM_CONNECTOR_ALLOWLIST_KEY,),
        ).fetchone()
        assert json.loads(row[0]) == ["github", "postgres"]
    finally:
        conn.close()


def test_unknown_catalog_providers() -> None:
    catalog = get_connector_catalog()
    services = catalog.service_ids()
    assert unknown_catalog_providers("*", services) == []
    unknown = unknown_catalog_providers(["postgres", "not-a-real-connector"], services)
    assert "not-a-real-connector" in unknown
    with pytest.raises(ValueError, match="Unknown connector"):
        assert_allowed_providers_in_catalog(["not-a-real-connector"], services)


def test_category_breakdown_counts(tmp_path: Path) -> None:
    conn = _fresh_db(tmp_path)
    try:
        catalog = __import__(
            "basis.services.connector.catalog",
            fromlist=["get_connector_catalog"],
        ).get_connector_catalog()
        rows = catalog.category_breakdown(platform_allowed=["postgres"])
        assert isinstance(rows, list)
        if rows:
            assert "category" in rows[0] and "total" in rows[0] and "enabled" in rows[0]
    finally:
        conn.close()


def test_platform_settings_connectors_http(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "http_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    summary = client.get("/api/v1/settings/connectors", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["allowed_providers"] == "*"

    bad = client.put(
        "/api/v1/settings/connectors",
        headers=headers,
        json={"allowed_providers": ["not-a-real-connector"]},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "connector_unknown_providers"

    validate = client.post(
        "/api/v1/settings/connectors/validate",
        headers=headers,
        json={"allowed_providers": ["postgres", "ghost"]},
    )
    assert validate.status_code == 200
    body = validate.json()
    assert body["ok"] is False
    assert "ghost" in body["unknown_providers"]

    ok = client.put(
        "/api/v1/settings/connectors",
        headers=headers,
        json={"allowed_providers": ["postgres", "mysql"]},
    )
    assert ok.status_code == 200
    assert ok.json()["allowed_providers"] == ["mysql", "postgres"]

    stats = client.get("/api/v1/settings/connectors/catalog/stats", headers=headers)
    assert stats.status_code == 200
    assert isinstance(stats.json()["category_breakdown"], list)


def test_runtime_respects_platform_ceiling(tmp_path: Path) -> None:
    conn = _fresh_db(tmp_path)
    try:
        conn.execute(
            "INSERT INTO workspaces (id, name, description, visibility, created_by, created_at) "
            "VALUES ('kb1', 'KB', '', 'private', 'u1', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
        upsert_platform_allowed_providers(conn, ["postgres"])
        vault = ConnectorAuthVault(conn, vault_secret="secret")
        vault.upsert_policy("kb1", allowed_providers="*")
        runtime = ConnectorRuntime(conn, vault_secret="secret")
        with pytest.raises(PermissionError, match="platform connector policy"):
            runtime.vault.assert_service_allowed("kb1", "mysql")
        with pytest.raises(PermissionError, match="platform level"):
            vault.upsert_policy("kb1", allowed_providers=["mysql"])
    finally:
        conn.close()


def test_workspace_catalog_browse_and_enable_provider_http(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "browse_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    narrow = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy",
        headers=headers,
        json={"allowed_providers": ["postgres"], "action_policy": {}},
    )
    assert narrow.status_code == 200

    cat = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog",
        headers=headers,
        params={"has_streams_only": False, "limit": 200},
    )
    assert cat.status_code == 200
    body = cat.json()
    catalog_services = {c["service"] for c in body["connectors"]}
    app_services = {c["service"] for c in body["workspace_apps"]}
    assert "postgres" in app_services
    assert "postgres" in catalog_services
    assert "github" in catalog_services
    assert "github" not in app_services

    enable = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy/providers/github/enable",
        headers=headers,
    )
    assert enable.status_code == 200
    assert "github" in enable.json()["effective_allowed_providers"]

    cat2 = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog",
        headers=headers,
        params={"has_streams_only": False, "limit": 200},
    )
    app_services2 = {c["service"] for c in cat2.json()["workspace_apps"]}
    assert "github" in app_services2

    soft_disable = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy/providers/github/disable",
        headers=headers,
    )
    assert soft_disable.status_code == 200
    assert "github" in soft_disable.json()["installed_providers"]
    assert "github" in soft_disable.json()["disabled_providers"]
    assert "github" not in soft_disable.json()["effective_allowed_providers"]

    cat3 = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog",
        headers=headers,
        params={"has_streams_only": False, "limit": 200},
    )
    assert "github" in {c["service"] for c in cat3.json()["workspace_apps"]}

    re_enable = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/policy/providers/github/enable",
        headers=headers,
    )
    assert re_enable.status_code == 200
    assert "github" in re_enable.json()["effective_allowed_providers"]
    assert "github" not in re_enable.json()["disabled_providers"]
