"""Whether a scheduled governor pass is due (interval from governance config)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from basis.services.knowledge.models import GovernanceConfig
from basis.services.knowledge.services.ingest_source_service import is_ingest_poll_due


def is_governor_due(config: GovernanceConfig, now: datetime) -> bool:
    if not config.governor_enabled:
        return False
    if config.governor_interval_minutes <= 0:
        return False
    pseudo_source: dict[str, Any] = {
        "config": {
            "poll_interval_minutes": config.governor_interval_minutes,
            "last_sync_at": config.governor_last_run_at,
        },
    }
    return is_ingest_poll_due(pseudo_source, now)
