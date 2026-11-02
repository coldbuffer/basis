"""One-line JSON ready events on stderr for process supervisors (Desktop / Electron)."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from basis.infra.runtime.config import Settings


def emit_process_ready(settings: Settings) -> None:
    """Emit ``basis.ready`` (and ``gateway.ready`` on desktop) for shell parsers.

    Uvicorn only configures its own loggers; ``logging.getLogger("basis")`` may
    have no handler unless ``BASIS_LOG_JSON=1``. Always print a single JSON line
    per event to stderr (Fellow ``gateway.ready`` convention).
    """
    payload: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "profile": settings.deployment_profile,
    }
    events = ["basis.ready"]
    if settings.is_desktop:
        events.append("gateway.ready")
    log = logging.getLogger("basis")
    for event in events:
        line = json.dumps({"event": event, **payload}, ensure_ascii=False)
        log.info(line)
        print(line, file=sys.stderr, flush=True)
