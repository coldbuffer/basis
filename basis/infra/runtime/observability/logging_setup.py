"""Central logging configuration for the API process (X-02)."""

from __future__ import annotations

from basis.interface.http.shared.request_id import install_request_id_logging
from basis.infra.runtime.config import Settings
from basis.infra.runtime.observability.json_logging import install_json_logging
from basis.infra.runtime.observability.uvicorn_logging import build_uvicorn_log_config


def configure_basis_logging(settings: Settings) -> None:
    install_request_id_logging()
    if settings.log_json:
        install_json_logging()


def uvicorn_log_config(settings: Settings) -> dict | None:
    """Pass to ``uvicorn.run(log_config=...)`` when JSON logging is enabled."""
    if not settings.log_json:
        return None
    return build_uvicorn_log_config()
