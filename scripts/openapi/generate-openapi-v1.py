#!/usr/bin/env python3
"""Write OpenAPI v1 JSON snapshots from the live FastAPI app.

Runtime `/openapi/v1.json` is exported directly from `app.openapi()` (see
`basis.interface.contract.openapi.v1_export`). This script writes the same export to
`openapi/*.json` for CI drift checks and `web` `gen:openapi-types`.

Operation `description` fields come from route handler docstrings only (FastAPI).
See docs/architecture/openapi-v1.md §2 (two surfaces).

Uses a fresh SQLite data dir by default (ignores repo `.env` Postgres). If you pass
`--data-dir`, clear it yourself when migrations change checksums.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from copy import deepcopy
from pathlib import Path

from basis.interface.http.app import create_app
from basis.interface.contract.openapi.v1_export import (
    export_openapi_v1_document,
    filter_openapi_paths,
)
from basis.infra.runtime.config import Settings


def build_openapi_v1(*, data_dir: Path) -> dict:
    app = create_app(Settings(data_dir=data_dir))
    return export_openapi_v1_document(app, assert_descriptions=True)


def _write_json(path: Path, schema: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/tmp/basis-openapi-gen"),
        help="Temporary data dir for create_app (default: /tmp/basis-openapi-gen)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("openapi"),
        help="Directory for basis-v1*.json (default: openapi/)",
    )
    args = parser.parse_args()
    default_data_dir = Path("/tmp/basis-openapi-gen")
    if args.data_dir == default_data_dir and default_data_dir.exists():
        shutil.rmtree(default_data_dir)
    args.data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["BASIS_DATABASE_URL"] = ""
    full = build_openapi_v1(data_dir=args.data_dir)
    out_dir = args.out_dir

    full_path = out_dir / "basis-v1.json"
    _write_json(full_path, full)
    print(f"Wrote {full_path} ({len(full['paths'])} paths)")

    for name, surfaces in (
        ("basis-v1-platform.json", {"public", "platform"}),
        ("basis-v1-workspaces.json", {"public", "workspaces"}),
    ):
        part = deepcopy(full)
        part["paths"] = filter_openapi_paths(full["paths"], surfaces)
        part["info"] = deepcopy(full["info"])
        slug = name.replace("basis-v1-", "").replace(".json", "")
        part["info"]["title"] = f"Basis API — {slug}"
        out = out_dir / name
        _write_json(out, part)
        print(f"Wrote {out} ({len(part['paths'])} paths)")


if __name__ == "__main__":
    main()
