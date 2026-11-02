"""Load deployment profiles (Fellow-style YAML) into process environment."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR = re.compile(r"\$([A-Z_][A-Z0-9_]*)")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DESKTOP_PROFILE = _REPO_ROOT / "contracts" / "profiles" / "profile.desktop.yaml"


def repo_root() -> Path:
    return _REPO_ROOT


def default_desktop_profile_path() -> Path:
    return _DEFAULT_DESKTOP_PROFILE


def _expand_env(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return os.environ.get(key, "")

    return _ENV_VAR.sub(repl, value)


def _expand_tree(node: Any) -> Any:
    if isinstance(node, str):
        return _expand_env(node)
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    return node


def load_profile_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Profile must be a mapping: {path}")
    return _expand_tree(data)


def _basis_home() -> Path:
    raw = os.environ.get("BASIS_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".basis"


def apply_profile_dict(profile: dict[str, Any]) -> None:
    """Set BASIS_* env vars from a loaded profile (does not clear unrelated vars)."""
    deployment = profile.get("deployment") or {}
    auth = profile.get("auth") or {}
    server = profile.get("server") or {}
    database = profile.get("database") or {}
    storage = profile.get("storage") or {}

    profile_name = str(deployment.get("profile") or "server").strip().lower()
    os.environ["BASIS_DEPLOYMENT_PROFILE"] = profile_name

    if auth.get("enabled") is False:
        os.environ["BASIS_AUTH_ENABLED"] = "0"
    elif auth.get("enabled") is True:
        os.environ["BASIS_AUTH_ENABLED"] = "1"

    host = server.get("host")
    if host is not None:
        os.environ["BASIS_HOST"] = str(host).strip()

    port = server.get("port")
    if port is not None and os.environ.get("BASIS_LISTEN_PORT_RESOLVED") != "1":
        pinned = os.environ.get("BASIS_PORT", "").strip()
        if os.environ.get("BASIS_E2E") == "1" and pinned and pinned != "0":
            pass
        else:
            os.environ["BASIS_PORT"] = str(int(port))

    home = _basis_home()
    os.environ.setdefault("BASIS_HOME", str(home))

    storage_root = storage.get("root")
    if storage_root and str(storage_root).strip():
        data_dir = Path(str(storage_root)).expanduser()
    else:
        data_dir = home
    os.environ.setdefault("BASIS_DATA_DIR", str(data_dir))

    db_path = database.get("path")
    if db_path and str(db_path).strip():
        sqlite_path = Path(str(db_path)).expanduser()
    else:
        sqlite_path = data_dir / "basis.db"
    os.environ.setdefault("BASIS_SQLITE_PATH", str(sqlite_path))

    if database.get("driver") == "sqlite":
        os.environ.pop("BASIS_DATABASE_URL", None)


def resolve_profile_path(spec: str | None) -> Path | None:
    if spec is None or not str(spec).strip():
        env_path = os.environ.get("BASIS_PROFILE_PATH", "").strip()
        if env_path:
            return Path(env_path).expanduser()
        if os.environ.get("BASIS_DEPLOYMENT_PROFILE", "").strip().lower() == "desktop":
            return _DEFAULT_DESKTOP_PROFILE
        return None
    spec = spec.strip()
    if spec in ("desktop", "profile.desktop", "profile.desktop.yaml"):
        return _DEFAULT_DESKTOP_PROFILE
    path = Path(spec).expanduser()
    if path.is_file():
        return path
    candidate = _REPO_ROOT / "contracts" / "profiles" / spec
    if candidate.is_file():
        return candidate
    candidate_yaml = candidate.with_suffix(".yaml")
    if candidate_yaml.is_file():
        return candidate_yaml
    raise FileNotFoundError(f"Profile not found: {spec}")


def bootstrap_profile_from_env(profile_spec: str | None = None) -> Path | None:
    """Load profile file into os.environ before Settings.from_env()."""
    spec = profile_spec if profile_spec is not None else os.environ.get("BASIS_PROFILE")
    path = resolve_profile_path(spec)
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(f"Profile not found: {path}")
    apply_profile_dict(load_profile_yaml(path))
    os.environ["BASIS_PROFILE_PATH"] = str(path.resolve())
    return path
