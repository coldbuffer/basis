"""Ontology hub catalog, graph, SKOS, SHACL, and registry routes."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic_core import PydanticUndefined

from basis.application.ontology import operations as ontology_ops
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.domain.knowledge.services.workspace_shacl import saved_shacl_turtle_for_ontology
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.shared.deps import (
    get_current_user,
    get_knowledge_store,
    get_workspace_for_role,
    get_store,
    save_graph,
)
from basis.domain.ontology.hub.scoped_state import OntologyHubState
from basis.domain.ontology.hub.create_write import create_ontology as create_ontology_write
from basis.domain.ontology.browse.graph_read import get_entity_detail as get_entity_detail_read
from basis.domain.ontology.hub.load_write import load_ontology as load_ontology_write
from basis.domain.ontology.browse.preview_read import preview_ontology as preview_ontology_read
from basis.domain.ontology.browse.health_read import ontology_health as ontology_health_read
from basis.domain.ontology.hub.refresh_write import refresh_ontology as refresh_ontology_write
from basis.domain.ontology.hub.registry_write import remove_ontology as remove_ontology_write
from basis.domain.ontology.shacl.shacl_read import (
    generate_shacl as generate_shacl_read,
    list_shacl_shapes as list_shacl_shapes_read,
    validate_shacl as validate_shacl_read,
)
from basis.domain.ontology.browse.skos_read import (
    get_skos_concept as get_skos_concept_read,
    list_skos_schemes as list_skos_schemes_read,
    search_skos_concepts as search_skos_concepts_read,
)
from basis.domain.ontology.hub.hub_models import (
    CreateOntologyRequest,
    LoadOntologyRequest,
    PreviewOntologyRequest,
    ShaclGenerateRequest,
    ShaclValidateRequest,
    SKOSConceptSearchRequest,
)
from basis.domain.ontology.rdf_io import (
    content_likely_owl_schema,
    convert_ontology_to_graph,
    fetch_ontology_url_bytes,
    parse_rdf_sync_for_basis,
)
from basis.interface.http.workspace.ontology.ontology_application_http import run_ontology_operation
from basis.interface.http.workspace.ontology.ontology_hub_support import (
    audit_ontology_graph_write,
    min_role,
    ontology_session,
)


def register_ontology_hub_catalog_routes(router: APIRouter) -> None:
    async def _ont_1_preview_ontology(
        workspace_id: str,
        request: Request,
        body: PreviewOntologyRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Preview Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        with OntologyHubState(request, workspace_id):
            return await asyncio.to_thread(
                preview_ontology_read,
                url=body.url,
                content=body.content,
                format=body.format,
                fetch_url_bytes=fetch_ontology_url_bytes,
                parse_rdf_sync=parse_rdf_sync_for_basis,
            )

    router.add_api_route("/{workspace_id}/ontology/preview", _ont_1_preview_ontology, methods=["POST"], name="_ont_1_preview_ontology")

    async def _ont_2_load_ontology(
        workspace_id: str,
        request: Request,
        body: LoadOntologyRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Load Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await asyncio.to_thread(
                load_ontology_write,
                session,
                registry,
                url=body.url,
                content=body.content,
                format=body.format,
                name=body.name,
                description=body.description,
                tags=list(body.tags) if body.tags else None,
                fetch_url_bytes=fetch_ontology_url_bytes,
                parse_rdf_sync=parse_rdf_sync_for_basis,
                content_likely_owl=content_likely_owl_schema,
                convert_ontology_to_graph=convert_ontology_to_graph,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            audit_ontology_graph_write(store, user, workspace_id, "workspace.graph.ontology_load", result)
            return result

    router.add_api_route("/{workspace_id}/ontology/load", _ont_2_load_ontology, methods=["POST"], name="_ont_2_load_ontology")

    async def _ont_3_create_ontology(
        workspace_id: str,
        request: Request,
        body: CreateOntologyRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Create Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await asyncio.to_thread(
                create_ontology_write,
                session,
                registry,
                namespace=body.namespace,
                name=body.name,
                description=body.description,
                tags=list(body.tags) if body.tags else None,
                mode=body.mode,
                sample_data=body.sample_data,
                schema_text=body.schema_text,
                provider=body.provider,
                model=body.model,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            audit_ontology_graph_write(store, user, workspace_id, "workspace.graph.ontology_create", result)
            return result

    router.add_api_route("/{workspace_id}/ontology/create", _ont_3_create_ontology, methods=["POST"], name="_ont_3_create_ontology")

    async def _ont_4_search_entities(
        workspace_id: str,
        request: Request,
        q: str = Query(PydanticUndefined),
        entity_type: Optional[str] = Query(None),
        limit: int = Query(50),
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Search Entities. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        args: dict[str, Any] = {"q": q, "limit": limit}
        if entity_type:
            args["entity_type"] = entity_type
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_search_ontology_entities,
            args,
            http_method="GET",
        )
        return payload.get("results", [])

    router.add_api_route("/{workspace_id}/ontology/search", _ont_4_search_entities, methods=["GET"], name="_ont_4_search_entities")

    async def _ont_5_get_ontology_graph(
        workspace_id: str,
        request: Request,
        uri: str = Query(PydanticUndefined),
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Get Ontology Graph. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_get_ontology_graph,
            {"uri": uri},
            http_method="GET",
        )
        return payload.get("graph", payload)

    router.add_api_route("/{workspace_id}/ontology/graph", _ont_5_get_ontology_graph, methods=["GET"], name="_ont_5_get_ontology_graph")

    async def _ont_6_get_entity_detail(
        workspace_id: str,
        request: Request,
        entity_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Get Entity Detail. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("GET"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            return await asyncio.to_thread(
                get_entity_detail_read,
                session,
                registry,
                entity_uri=entity_uri,
            )

    router.add_api_route("/{workspace_id}/ontology/entity/{entity_uri:path}", _ont_6_get_entity_detail, methods=["GET"], name="_ont_6_get_entity_detail")

    async def _ont_7_list_skos_schemes(
        workspace_id: str,
        request: Request,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
List Skos Schemes. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("GET"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            return await asyncio.to_thread(list_skos_schemes_read, session)

    router.add_api_route("/{workspace_id}/ontology/skos/schemes", _ont_7_list_skos_schemes, methods=["GET"], name="_ont_7_list_skos_schemes")

    async def _ont_8_search_skos_concepts(
        workspace_id: str,
        request: Request,
        body: SKOSConceptSearchRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Search Skos Concepts. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            result = await asyncio.to_thread(
                search_skos_concepts_read,
                session,
                query=body.query,
                scheme_uri=body.scheme_uri,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            return result

    router.add_api_route("/{workspace_id}/ontology/skos/search", _ont_8_search_skos_concepts, methods=["POST"], name="_ont_8_search_skos_concepts")

    async def _ont_9_get_skos_concept(
        workspace_id: str,
        request: Request,
        concept_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Get Skos Concept. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("GET"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            return await asyncio.to_thread(get_skos_concept_read, session, concept_uri)

    router.add_api_route("/{workspace_id}/ontology/skos/concept/{concept_uri:path}", _ont_9_get_skos_concept, methods=["GET"], name="_ont_9_get_skos_concept")

    async def _ont_10_ontology_health(
        workspace_id: str,
        request: Request,
        uri: str = Query(PydanticUndefined),
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Ontology Health. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("GET"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            alignments = request.app.state.ontology_alignments[workspace_id]
            return await ontology_health_read(session, registry, alignments, uri=uri)

    router.add_api_route("/{workspace_id}/ontology/health", _ont_10_ontology_health, methods=["GET"], name="_ont_10_ontology_health")

    async def _ont_11_generate_shacl(
        workspace_id: str,
        request: Request,
        body: ShaclGenerateRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Generate Shacl. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await generate_shacl_read(
                session,
                registry,
                uri=body.uri,
                quality_tier=body.quality_tier,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            return result

    router.add_api_route("/{workspace_id}/ontology/shacl/generate", _ont_11_generate_shacl, methods=["POST"], name="_ont_11_generate_shacl")

    async def _ont_12_list_shacl_shapes(
        workspace_id: str,
        request: Request,
        uri: str = Query(PydanticUndefined),
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
        knowledge: KnowledgeStore = Depends(get_knowledge_store),
    ) -> Any:
        """
List Shacl Shapes. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("GET"))
        session = ontology_session(request, workspace_id)
        saved = saved_shacl_turtle_for_ontology(knowledge, workspace_id, uri)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            return await list_shacl_shapes_read(
                session,
                registry,
                uri=uri,
                shacl_turtle_override=saved,
            )

    router.add_api_route("/{workspace_id}/ontology/shacl/shapes", _ont_12_list_shacl_shapes, methods=["GET"], name="_ont_12_list_shacl_shapes")

    async def _ont_13_validate_shacl(
        workspace_id: str,
        request: Request,
        body: ShaclValidateRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Validate Shacl. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await validate_shacl_read(
                session,
                registry,
                uri=body.uri,
                shacl_turtle=body.shacl_turtle,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            return result

    router.add_api_route("/{workspace_id}/ontology/shacl/validate", _ont_13_validate_shacl, methods=["POST"], name="_ont_13_validate_shacl")

    async def _ont_14_remove_ontology(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Remove Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("DELETE"))
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await asyncio.to_thread(remove_ontology_write, registry, ontology_uri)
            from basis.interface.http.shared.deps import rebuild_graph_projection

            rebuild_graph_projection(request, workspace_id)
            audit_ontology_graph_write(
                store, user, workspace_id, "workspace.graph.ontology_remove", {"ontology_uri": ontology_uri}
            )
            return result

    router.add_api_route("/{workspace_id}/ontology/{ontology_uri:path}", _ont_14_remove_ontology, methods=["DELETE"], name="_ont_14_remove_ontology")

    async def _ont_15_toggle_ontology(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Toggle Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        return await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_toggle_ontology,
            {"ontology_uri": ontology_uri},
            http_method="PATCH",
            require_editor=True,
        )

    router.add_api_route("/{workspace_id}/ontology/{ontology_uri:path}/toggle", _ont_15_toggle_ontology, methods=["PATCH"], name="_ont_15_toggle_ontology")

    async def _ont_16_refresh_ontology(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Refresh Ontology. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        get_workspace_for_role(request, user, workspace_id, store, min_role("POST"))
        session = ontology_session(request, workspace_id)
        with OntologyHubState(request, workspace_id):
            registry = request.app.state.ontology_registries[workspace_id]
            result = await asyncio.to_thread(
                refresh_ontology_write,
                session,
                registry,
                ontology_uri,
                fetch_url_bytes=fetch_ontology_url_bytes,
                parse_rdf_sync=parse_rdf_sync_for_basis,
            )
            save_graph(request, workspace_id, sync_ledger=False)
            return result

    router.add_api_route("/{workspace_id}/ontology/{ontology_uri:path}/refresh", _ont_16_refresh_ontology, methods=["POST"], name="_ont_16_refresh_ontology")
