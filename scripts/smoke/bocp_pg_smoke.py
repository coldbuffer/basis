#!/usr/bin/env python3
"""Minimal BOCP inbound sync smoke against the configured Basis API (Postgres dev).

Usage (from repo root, API running, `.env` loaded):

  uv run python scripts/smoke/bocp_pg_smoke.py \\
    --kb-id 108dd8a0-297b-4c37-862f-f47da99ae4f3 \\
    --mapping-id stm_4f4c87edb0b941ed

Optional:
  --mcp              sync via MCP tools/call
  --scan-conflicts   POST …/review/scan-statement-conflicts after sync
  --list-review      print open review queue counts by kind
  --writeback ENTITY --set tier=gold   propose connector writeback (review queue)
  --approve-writeback   approve first open connector_writeback review item

Live writeback loop (Postgres `public.customers`, writable column `tier` only):

  uv run python scripts/smoke/bocp_pg_smoke.py --kb-id … --mapping-id … --skip-sync \\
    --writeback ent_… --set tier=platinum --approve-writeback
  uv run python scripts/smoke/bocp_pg_smoke.py --kb-id … --mapping-id …   # re-sync → unchanged
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any

import httpx

from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def _issue_owner_token(workspace_id: str) -> str:
    store = create_app(Settings.from_env()).state.store
    row = store._conn.execute(
        "SELECT user_id FROM members WHERE workspace_id = ? AND role = 'owner' LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"No owner for workspace {workspace_id}")
    token = store._issue_token(row[0])
    store._conn.commit()
    return token


def _sync_mapping(
    *,
    base: str,
    workspace_id: str,
    mapping_id: str,
    headers: dict[str, str],
    use_mcp: bool,
) -> dict[str, Any]:
    if use_mcp:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "sync_connector_table_mapping",
                "arguments": {"mapping_id": mapping_id},
            },
        }
        r = httpx.post(
            f"{base}/api/v1/workspaces/{workspace_id}/mcp",
            headers=headers,
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise SystemExit(json.dumps(body, indent=2))
        return json.loads(body["result"]["content"][0]["text"])
    r = httpx.post(
        f"{base}/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}/sync",
        headers=headers,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _list_review_items(
    base: str,
    workspace_id: str,
    headers: dict[str, str],
    *,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"status": "open", "limit": 200}
    if kind:
        params["kind"] = kind
    r = httpx.get(
        f"{base}/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params=params,
        timeout=60,
    )
    r.raise_for_status()
    return list(r.json().get("items") or [])


def _list_review_summary(base: str, workspace_id: str, headers: dict[str, str]) -> dict[str, int]:
    items = _list_review_items(base, workspace_id, headers)
    counts = Counter(str(item.get("kind") or "?") for item in items)
    return dict(counts)


def _approve_review_item(
    base: str,
    workspace_id: str,
    headers: dict[str, str],
    item_id: str,
    *,
    keeper_statement_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if keeper_statement_id:
        body["keeper_statement_id"] = keeper_statement_id
    r = httpx.post(
        f"{base}/api/v1/workspaces/{workspace_id}/review/items/{item_id}/approve",
        headers=headers,
        json=body,
        timeout=120,
    )
    if r.status_code >= 400:
        raise SystemExit(f"review approve failed {r.status_code}: {r.text}")
    return r.json()


def _scan_conflicts(base: str, workspace_id: str, headers: dict[str, str]) -> dict[str, Any]:
    r = httpx.post(
        f"{base}/api/v1/workspaces/{workspace_id}/review/scan-statement-conflicts",
        headers=headers,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _propose_writeback(
    base: str,
    workspace_id: str,
    headers: dict[str, str],
    entity_id: str,
    field_updates: dict[str, Any],
) -> dict[str, Any]:
    r = httpx.post(
        f"{base}/api/v1/workspaces/{workspace_id}/connectors/outbox/propose",
        headers=headers,
        json={"entity_id": entity_id, "field_updates": field_updates},
        timeout=120,
    )
    if r.status_code >= 400:
        raise SystemExit(f"writeback propose failed {r.status_code}: {r.text}")
    return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="BOCP inbound sync smoke")
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--mapping-id", required=True)
    parser.add_argument("--mcp", action="store_true", help="Use MCP tools/call sync")
    parser.add_argument(
        "--scan-conflicts",
        action="store_true",
        help="POST review/scan-statement-conflicts after sync",
    )
    parser.add_argument(
        "--list-review",
        action="store_true",
        help="Print open review item counts by kind (after other steps)",
    )
    parser.add_argument(
        "--writeback",
        metavar="ENTITY_ID",
        help="Propose connector writeback for entity (enters review when writeback_mode=review)",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="COL=VALUE",
        default=[],
        help="Field update for --writeback (repeatable)",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Only run --list-review / --scan-conflicts / --writeback",
    )
    parser.add_argument(
        "--approve-writeback",
        action="store_true",
        help="Approve the first open connector_writeback review item",
    )
    args = parser.parse_args()

    if args.writeback and not args.set:
        parser.error("--writeback requires at least one --set COL=VALUE")

    settings = Settings.from_env()
    base = f"http://{settings.host}:{settings.port}"
    token = _issue_owner_token(args.workspace_id)
    headers = {"Authorization": f"Bearer {token}"}

    health = httpx.get(f"{base}/health", timeout=30)
    health.raise_for_status()
    print("health:", health.json())

    if not args.skip_sync:
        stats = _sync_mapping(
            base=base,
            workspace_id=args.workspace_id,
            mapping_id=args.mapping_id,
            headers=headers,
            use_mcp=args.mcp,
        )
        print("sync:", json.dumps(stats, indent=2, default=str))

    if args.scan_conflicts:
        scan = _scan_conflicts(base, args.workspace_id, headers)
        print("scan_conflicts:", json.dumps(scan, indent=2, default=str))

    if args.writeback:
        updates: dict[str, Any] = {}
        for pair in args.set:
            if "=" not in pair:
                raise SystemExit(f"bad --set value: {pair}")
            col, val = pair.split("=", 1)
            updates[col.strip()] = val.strip()
        wb = _propose_writeback(base, args.workspace_id, headers, args.writeback, updates)
        print("writeback:", json.dumps(wb, indent=2, default=str))

    if args.approve_writeback:
        writebacks = _list_review_items(
            base, args.workspace_id, headers, kind="connector_writeback"
        )
        if not writebacks:
            raise SystemExit("no open connector_writeback review items")
        item_id = str(writebacks[0]["id"])
        approved = _approve_review_item(base, args.workspace_id, headers, item_id)
        print("approve_writeback:", json.dumps(approved, indent=2, default=str))

    if args.list_review or args.scan_conflicts or args.writeback or args.approve_writeback:
        summary = _list_review_summary(base, args.workspace_id, headers)
        print("open_review_by_kind:", json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
