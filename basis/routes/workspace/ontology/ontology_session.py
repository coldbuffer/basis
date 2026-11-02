"""Workspace graph graph session helper for workspace ontology/vocabulary routes."""

from __future__ import annotations

from fastapi import Request

from basis.http.deps import graph_runtime_for
from basis.services.graph.session.guard import require_graph_session


def graph_session(request: Request, workspace_id: str):
    runtime = graph_runtime_for(request, workspace_id)
    return require_graph_session(runtime)
