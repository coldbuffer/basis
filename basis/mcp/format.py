"""MCP tools/call result envelope (text JSON content)."""

from __future__ import annotations

import json
from typing import Any


def mcp_text_result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "isError": is_error,
    }
