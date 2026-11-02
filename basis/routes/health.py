import asyncio

from fastapi import APIRouter, Request

from basis import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/v1/health")
async def health(request: Request) -> dict[str, str]:
    """Liveness probe; verifies database connectivity and returns build version."""
    database = request.app.state.database
    await asyncio.to_thread(database.conn.execute, "SELECT 1")
    return {
        "status": "ok",
        "version": __version__,
        "database": database.backend,
    }
