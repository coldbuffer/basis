"""Runtime limit helpers for search operations."""

from __future__ import annotations

from typing import Any

from basis.services.kernel.context import WorkspaceCoreContext


def chunk_search_limit_max(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> int:
    if args.get("limit_max") is not None:
        return max(1, int(args["limit_max"]))
    if ctx.runtime_limits is not None:
        return ctx.runtime_limits.chunk_search_max_limit
    return 30


def graph_search_max_limit(ctx: WorkspaceCoreContext, args: dict[str, Any], limit: int) -> int:
    if args.get("max_limit") is not None:
        return max(limit, int(args["max_limit"]))
    if ctx.runtime_limits is not None:
        return max(limit, ctx.runtime_limits.graph_node_search_max_limit)
    return limit
