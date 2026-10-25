#!/usr/bin/env python3
"""Print provider migration tier stats (OpenConnector catalog × registry × shipped Basis)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PROVIDERS = REPO / "basis" / "domain" / "integration" / "providers"


def _normalize_service_id(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _anyconnect_service_ids(catalog_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in catalog_dir.glob("*.json"):
        ids.add(_normalize_service_id(path.stem))
    return ids


def _registry_id_set(raw_ids: set[str]) -> set[str]:
    return {_normalize_service_id(i) for i in raw_ids}


def _registry_services_and_modes(path: Path) -> tuple[set[str], Counter[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set(), Counter()
    modes: Counter[str] = Counter()
    ids: set[str] = set()
    for key, block in data.items():
        if not isinstance(block, dict):
            continue
        ids.add(str(key))
        mode = str(block.get("auth_mode") or "").upper()
        if mode:
            modes[mode] += 1
    return ids, modes


def _shipped_services() -> set[str]:
    if not PROVIDERS.is_dir():
        return set()
    return {p.stem for p in PROVIDERS.glob("*.yaml")}


def main() -> int:
    sys.path.insert(0, str(REPO))
    from basis.domain.connector.synthesis.paths import (
        connector_catalog_dir,
        legacy_anyconnect_catalog_dir,
        open_connector_catalog_dir,
        providers_registry_yaml,
    )
    from basis.domain.connector.synthesis.providers_registry_auth import (
        registry_auth_mode_to_bocp,
    )

    shipped = _shipped_services()
    registry_path = providers_registry_yaml()
    oc_dir = open_connector_catalog_dir()
    ac_dir = connector_catalog_dir()
    legacy_dir = legacy_anyconnect_catalog_dir()

    report: dict[str, object] = {
        "shipped_count": len(shipped),
        "shipped_services": sorted(shipped),
    }

    if registry_path is None:
        report["providers_registry"] = "missing (set BASIS_SYNTHESIS_PROVIDERS_REGISTRY)"
    else:
        registry_ids, registry_modes = _registry_services_and_modes(registry_path)
        bocp_modes = Counter(
            registry_auth_mode_to_bocp(m) for m in registry_modes.elements()
        )
        report["providers_registry"] = {
            "path": str(registry_path),
            "count": len(registry_ids),
            "auth_mode_upstream": dict(registry_modes.most_common()),
            "auth_mode_bocp": dict(bocp_modes.most_common()),
        }

    if oc_dir is not None:
        report["open_connector_catalog"] = {
            "path": str(oc_dir),
            "count": len(_anyconnect_service_ids(oc_dir)),
        }
    else:
        report["open_connector_catalog"] = (
            "missing (clone open-connector sibling and run generate:catalog, "
            "or set BASIS_SYNTHESIS_OPEN_CONNECTOR_ROOT)"
        )
    if legacy_dir is not None:
        report["legacy_anyconnect_catalog"] = {
            "path": str(legacy_dir),
            "count": len(_anyconnect_service_ids(legacy_dir)),
        }
    if ac_dir is None:
        report["connector_catalog_effective"] = (
            "missing (OpenConnector or BASIS_SYNTHESIS_ANYCONNECT_CATALOG)"
        )
    else:
        ac_ids = _anyconnect_service_ids(ac_dir)
        report["connector_catalog_effective"] = {"path": str(ac_dir), "count": len(ac_ids)}

    if registry_path and ac_dir:
        registry_raw, _ = _registry_services_and_modes(registry_path)
        registry_ids = _registry_id_set(registry_raw)
        ac_ids = _anyconnect_service_ids(ac_dir)
        overlap = registry_ids & ac_ids
        report["overlap_registry_anyconnect"] = len(overlap)
        report["registry_only"] = len(registry_ids - ac_ids)
        report["anyconnect_only"] = len(ac_ids - registry_ids)
        shipped_norm = {_normalize_service_id(s) for s in shipped}
        report["shipped_in_registry"] = sorted(shipped_norm & registry_ids)
        report["shipped_not_in_registry"] = sorted(shipped_norm - registry_ids)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
