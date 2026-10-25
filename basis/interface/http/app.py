"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from basis import __version__
from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore
from basis.interface.http.shared.health import router as health_router
from basis.interface.http.mount_v1 import register_v1_api_routers
from basis.infra.runtime.config import Settings
from basis.infra.runtime.limits import RuntimeLimits
from basis.infra.runtime.database import get_database
from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.graph.session.registry import GraphSessionRegistry
from basis.domain.knowledge.search import ChunkSearchService
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.tenancy.realtime.hub import GraphWsHub
from basis.domain.tenancy.realtime.tickets import RealtimeTicketStore
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.tooling.test_support.playwright_e2e import is_playwright_e2e_data_dir
from basis.interface.http.shared.middleware.legacy_api_gate import LegacyApiGateMiddleware
from basis.interface.http.shared.middleware.legacy_deprecation import (
    LegacyApiDeprecationMiddleware,
)
from basis.interface.http.shared.request_id import (
    RequestIdMiddleware,
    attach_request_id_to_detail,
)
from basis.interface.http.shared.rest_v1_concurrency import RestV1ConcurrencyMiddleware
from basis.interface.http.shared.openapi_v1 import router as openapi_v1_router
from basis.infra.runtime.observability.logging_setup import configure_basis_logging


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    from basis.infra.runtime.observability.process_ready import emit_process_ready

    settings = app.state.settings
    emit_process_ready(settings)
    tasks: list[asyncio.Task[None]] = []
    if graph_runtime_available():
        interval = max(30, app.state.settings.graph_session_evict_interval_seconds)

        async def _evict_loop() -> None:
            registry = app.state.graph_session_registry
            while True:
                await asyncio.sleep(interval)
                registry.evict_idle()

        tasks.append(asyncio.create_task(_evict_loop()))

    poll_tick = int(getattr(app.state.settings, "http_poll_tick_seconds", 0) or 0)
    if poll_tick > 0:
        from basis.domain.knowledge.schedulers.ingest_poll_scheduler import run_due_http_polls

        from basis.domain.knowledge.schedulers.connector_poll_scheduler import run_due_connector_syncs

        async def _poll_loop() -> None:
            while True:
                await asyncio.sleep(max(15, poll_tick))
                await asyncio.to_thread(run_due_http_polls, app)
                await asyncio.to_thread(run_due_connector_syncs, app)

        tasks.append(asyncio.create_task(_poll_loop()))

    governor_tick = int(getattr(app.state.settings, "governor_tick_seconds", 0) or 0)
    if governor_tick > 0:
        from basis.domain.knowledge.schedulers.governor_poll_scheduler import run_due_governor_passes

        async def _governor_loop() -> None:
            while True:
                await asyncio.sleep(max(60, governor_tick))
                await asyncio.to_thread(run_due_governor_passes, app)

        tasks.append(asyncio.create_task(_governor_loop()))

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        executor = getattr(app.state, "ingest_executor", None)
        if executor is not None:
            # Let in-flight ingest finish while the process still has DB handles open.
            executor.shutdown(wait=True, cancel_futures=False)


def _cors_allow_origins() -> list[str]:
    origins = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ]
    if os.environ.get("BASIS_E2E") == "1":
        for port in (5174, 5175):
            origins.extend(
                (
                    f"http://127.0.0.1:{port}",
                    f"http://localhost:{port}",
                )
            )
    return origins


def create_app(app_settings: Settings | None = None) -> FastAPI:
    app_settings = app_settings or Settings.from_env()
    app_settings.validate_for_startup()
    configure_basis_logging(app_settings)
    app = FastAPI(
        title="Basis API",
        version=__version__,
        lifespan=_app_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = app_settings
    app.state.limits = RuntimeLimits.from_settings(app_settings)
    app.state.ingest_executor = ThreadPoolExecutor(
        max_workers=max(1, app_settings.ingest_max_inflight),
        thread_name_prefix="ingest",
    )
    app.state.ingest_pending_slot = threading.Semaphore(
        max(1, app_settings.ingest_max_pending)
    )
    app.state.database = get_database(
        app_settings.effective_database_url,
        pool_size=app_settings.db_pool_size,
        max_overflow=app_settings.db_max_overflow,
        pool_timeout=app_settings.db_pool_timeout_seconds,
    )
    # Compatibility alias for integrations that still inspect app.state.
    app.state.sqlite_db = app.state.database
    app.state.store = AdminStore(app.state.database)
    if is_playwright_e2e_data_dir(app_settings.data_dir):
        from basis.infra.tooling.test_support.playwright_llm_extract import (
            ensure_playwright_e2e_chat_llm,
            install_playwright_e2e_graph_builder_stub,
        )

        ensure_playwright_e2e_chat_llm(app.state.store)
        install_playwright_e2e_graph_builder_stub()
    if app_settings.is_desktop:
        from basis.domain.tenancy.identity.desktop_principal import ensure_desktop_principal

        app.state.desktop_user = ensure_desktop_principal(app.state.store)
    app.state.graph_persistence = GraphPersistence(app_settings.data_dir)
    app.state.blob_store = BlobStore(app_settings.data_dir)
    app.state.knowledge_store = KnowledgeStore(app.state.database, app.state.blob_store)
    app.state.chunk_search = ChunkSearchService(
        app.state.knowledge_store,
        app.state.store,
        app_settings.data_dir,
    )
    app.state.graphs = {}
    app.state.graph_session_registry = GraphSessionRegistry(
        idle_seconds=app_settings.graph_session_idle_seconds,
    )
    app.state.realtime_tickets = RealtimeTicketStore()
    app.state.ws_hub = GraphWsHub()
    app.state.mcp_semaphore = asyncio.Semaphore(app_settings.mcp_max_inflight)
    app.state.rest_v1_semaphore = asyncio.Semaphore(app_settings.rest_v1_max_inflight)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(LegacyApiDeprecationMiddleware)
    app.add_middleware(
        LegacyApiGateMiddleware,
        legacy_enabled=app_settings.legacy_api_enabled,
    )
    app.add_middleware(RestV1ConcurrencyMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(AdminError)
    async def handle_admin_error(request: Request, exc: AdminError) -> JSONResponse:
        detail = attach_request_id_to_detail(
            request,
            {"code": exc.code, "message": exc.message},
        )
        return JSONResponse(status_code=exc.status, content={"detail": detail})

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            payload = attach_request_id_to_detail(request, dict(detail))
            return JSONResponse(status_code=exc.status_code, content={"detail": payload})
        if isinstance(detail, str):
            payload = attach_request_id_to_detail(request, {"message": detail})
            return JSONResponse(status_code=exc.status_code, content={"detail": payload})
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    app.include_router(health_router)
    register_v1_api_routers(
        app,
        legacy_api_enabled=app_settings.legacy_api_enabled,
        include_e2e_helpers=is_playwright_e2e_data_dir(app_settings.data_dir),
    )
    app.include_router(openapi_v1_router)

    return app
