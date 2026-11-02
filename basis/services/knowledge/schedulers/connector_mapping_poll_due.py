"""Polling schedule helpers for BOCP table mappings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from basis.services.knowledge.services.connector_sync import SourceTableMappingRecord
from basis.services.knowledge.services.ingest_source_service import is_ingest_poll_due


def poll_interval_minutes_for_mapping(mapping: SourceTableMappingRecord) -> int:
    raw = mapping.checkpoint.get("poll_interval_minutes")
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def is_connector_mapping_poll_due(mapping: SourceTableMappingRecord, now: datetime) -> bool:
    if mapping.status != "active":
        return False
    if mapping.sync_direction not in ("inbound", "bidirectional"):
        return False
    interval = poll_interval_minutes_for_mapping(mapping)
    if interval <= 0:
        return False
    pseudo_source: dict[str, Any] = {
        "config": {
            "poll_interval_minutes": interval,
            "last_sync_at": mapping.checkpoint.get("last_synced_at"),
        },
    }
    return is_ingest_poll_due(pseudo_source, now)
