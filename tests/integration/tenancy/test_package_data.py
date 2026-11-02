"""Installed wheel must include connector manifests and synthesis batch assets."""

from __future__ import annotations

import importlib.resources as pkg_resources

import pytest


def test_connector_provider_yaml_in_package_data() -> None:
    root = pkg_resources.files("basis.services.connector") / "providers"
    names = {p.name for p in root.iterdir() if p.is_file()}
    assert "github.yaml" in names
    assert "postgres.yaml" in names
    assert "qq_mail.yaml" in names


def test_qq_mail_provider_bundle_loads_with_mail_protocol() -> None:
    from basis.services.connector.catalog import ConnectorCatalog

    catalog = ConnectorCatalog.load_from_directory()
    manifest = catalog.get("qq_mail")
    assert manifest is not None
    assert manifest.spec is not None
    assert manifest.spec.protocol == "mail"
    assert len(manifest.procedure_actions()) == 12


def test_synthesis_batch_yaml_in_package_data() -> None:
    batches = pkg_resources.files("basis.services.connector.synthesis") / "batches"
    names = {p.name for p in batches.iterdir() if p.is_file()}
    assert "batch_0.yaml" in names


def test_synthesis_executor_index_in_package_data() -> None:
    index = pkg_resources.files("basis.services.connector.synthesis") / "executors-index.json"
    assert index.is_file()


def test_ops_db_migration_sql_in_package_data() -> None:
    migrations = pkg_resources.files("basis.infra.db") / "migrations"
    names = {p.name for p in migrations.iterdir() if p.is_file()}
    assert "0001_schema_baseline.sql" in names
    assert len(names) == 1
