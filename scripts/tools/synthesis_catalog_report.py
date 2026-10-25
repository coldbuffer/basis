#!/usr/bin/env python3
"""Report OpenConnector catalog + providers-registry coverage for synthesis."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from basis.domain.connector.synthesis.anyconnect_catalog import load_anyconnect_procedures
from basis.domain.connector.synthesis.executor_index import invoke_wire_for_action
from basis.domain.connector.synthesis.paths import (
    connector_catalog_dir,
    open_connector_catalog_dir,
    providers_registry_yaml,
)
from basis.domain.connector.synthesis.providers_registry_auth import (
    load_provider_registry_block,
)


def main() -> None:
    ac_dir = connector_catalog_dir()
    oc_dir = open_connector_catalog_dir()
    registry = providers_registry_yaml()
    print(f"open_connector_catalog={oc_dir or 'missing'}")
    print(f"connector_catalog_effective={ac_dir or 'missing'}")
    print(f"providers_registry={registry or 'missing'}")
    if ac_dir is None:
        sys.exit(1)
    services = sorted(p.stem.replace("-", "_") for p in ac_dir.glob("*.json"))
    registry_hits = 0
    invoke_ready = 0
    total_actions = 0
    for service in services:
        has_registry = load_provider_registry_block(service) is not None
        if has_registry:
            registry_hits += 1
        loaded = load_anyconnect_procedures(service)
        if not loaded:
            continue
        _, procedures = loaded
        total_actions += len(procedures)
        for proc in procedures:
            if invoke_wire_for_action(service, proc.id):
                invoke_ready += 1
    print(f"catalog_services={len(services)}")
    print(f"registry_auth_hits={registry_hits}")
    print(f"catalog_procedure_actions={total_actions}")
    print(f"invoke_wire_known={invoke_ready}")


if __name__ == "__main__":
    main()
