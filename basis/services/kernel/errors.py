"""Application-layer errors mapped to HTTP / MCP responses."""

from __future__ import annotations

from typing import Any


class CoreError(Exception):
    def __init__(self, detail: dict[str, Any], *, status_code: int = 403) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
