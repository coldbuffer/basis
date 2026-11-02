"""Workspace-scoped adapters for workspace ontology hub routes."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.ontology.ontology_hub_catalog import register_ontology_hub_catalog_routes
from basis.routes.workspace.ontology.ontology_hub_governance import register_ontology_hub_governance_routes


def register_ontology_hub_routes(router: APIRouter) -> None:
    register_ontology_hub_catalog_routes(router)
    register_ontology_hub_governance_routes(router)
