#!/usr/bin/env python3
"""Report BOCP provider bundle stats (P6 conformance helper)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from basis.domain.connector.catalog import ConnectorCatalog, default_providers_dir
from basis.domain.connector.provider_bundle import load_provider_bundle, provider_manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-tier",
        choices=("catalog", "beta", "ga"),
        help="Fail if any loaded provider is below this ship tier",
    )
    parser.add_argument("--batch", type=int, help="Only validate services in batch_N.yaml")
    args = parser.parse_args()

    services: list[str] | None = None
    if args.batch is not None:
        from basis.domain.connector.synthesis.batches import load_batch

        services = load_batch(args.batch).services

    root = default_providers_dir()
    catalog = ConnectorCatalog.load_from_directory(root)
    tier_rank = {"catalog": 0, "beta": 1, "ga": 2}

    rows: list[tuple[str, str, int, int]] = []
    for manifest in catalog.list_manifests():
        if services is not None and manifest.service not in services:
            continue
        path = provider_manifest_path(root, manifest.service)
        loaded = load_provider_bundle(path)
        raw = loaded.manifest.model_dump(mode="python")
        tier = str(raw.get("x-basis-ship-tier") or "unknown")
        entities = len(manifest.entity_actions())
        procedures = len(manifest.procedure_actions())
        rows.append((manifest.service, tier, entities, procedures))

    print(f"providers={len(rows)}")
    for service, tier, entities, procedures in sorted(rows):
        print(f"  {service}: tier={tier} entities={entities} procedures={procedures}")

    if args.min_tier:
        need = tier_rank[args.min_tier]
        bad = [s for s, t, _, _ in rows if tier_rank.get(t, -1) < need]
        if bad:
            print(f"FAIL: below min tier {args.min_tier}: {', '.join(bad)}", file=sys.stderr)
            sys.exit(1)
    stats = catalog.summary_stats()
    print(f"summary: {stats}")


if __name__ == "__main__":
    main()
