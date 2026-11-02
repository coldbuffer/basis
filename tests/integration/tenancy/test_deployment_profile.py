"""Deployment profile YAML (Fellow-aligned desktop profile)."""

import os
from pathlib import Path

import pytest

from basis.infra.runtime.deployment_profile import (
    apply_profile_dict,
    bootstrap_profile_from_env,
    default_desktop_profile_path,
    load_profile_yaml,
    repo_root,
)


def test_default_desktop_profile_exists() -> None:
    path = default_desktop_profile_path()
    assert path.is_file()
    assert path.parent == repo_root() / "contracts" / "profiles"


def test_load_desktop_profile_auth_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASIS_HOME", str(tmp_path))
    profile = load_profile_yaml(default_desktop_profile_path())
    assert profile["deployment"]["profile"] == "desktop"
    assert profile["auth"]["enabled"] is False


def test_apply_profile_sets_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BASIS_DATA_DIR", raising=False)
    monkeypatch.setenv("BASIS_HOME", str(tmp_path))
    profile = load_profile_yaml(default_desktop_profile_path())
    apply_profile_dict(profile)
    assert os.environ["BASIS_DEPLOYMENT_PROFILE"] == "desktop"
    assert os.environ["BASIS_HOST"] == "127.0.0.1"
    assert os.environ["BASIS_PORT"] == "0"
    assert os.environ["BASIS_DATA_DIR"] == str(tmp_path)


def test_bootstrap_profile_desktop_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASIS_HOME", str(tmp_path))
    path = bootstrap_profile_from_env("desktop")
    assert path is not None
    assert os.environ["BASIS_DEPLOYMENT_PROFILE"] == "desktop"
