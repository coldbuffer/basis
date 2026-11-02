"""Background HTTP poll for ingest sources."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from basis.services.knowledge.services.ingest_source_service import (
    execute_ingest_source_sync,
    is_ingest_poll_due,
)
from basis.infra.observability.log_context import correlation_log_extra

logger = logging.getLogger(__name__)


def run_due_http_polls(app: FastAPI) -> int:
    """Run all due http_poll sources once. Returns count executed."""
    knowledge = app.state.knowledge_store
    now = datetime.now(timezone.utc)
    sources = knowledge.list_scheduled_ingest_sources_global()
    ran = 0
    for source in sources:
        if not is_ingest_poll_due(source, now):
            continue
        workspace_id = source["workspace_id"]
        source_id = source["id"]
        try:
            execute_ingest_source_sync(app, knowledge, workspace_id, source_id, auto_process=True)
            ran += 1
        except Exception:
            logger.exception(
                "scheduled ingest failed kb=%s source=%s kind=%s",
                workspace_id,
                source_id,
                source.get("kind"),
                extra=correlation_log_extra(workspace_id=workspace_id, source_id=source_id),
            )
    return ran
