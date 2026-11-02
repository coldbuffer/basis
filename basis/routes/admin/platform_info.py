"""Runtime info: Basis API + embedded semantica SDK (not a separate semantica HTTP server)."""

from fastapi import APIRouter

from basis import __version__
from basis.infra.runtime.capabilities import platform_capabilities

router = APIRouter(tags=["platform"])


@router.get("")
async def platform_info() -> dict:
    """Platform Info. Requires session JWT (`sessionAuth`)."""
    try:
        import semantica

        sdk_version = semantica.__version__
    except ImportError:
        sdk_version = None
    return {
        "basis_version": __version__,
        "semantica_sdk_version": sdk_version,
        "mode": "embedded_sdk",
        "capabilities": platform_capabilities(),
        "note": "图谱与推理在本 API 进程内通过 semantica Python 库执行，无需 semantica server start。",
    }
