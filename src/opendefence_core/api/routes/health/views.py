"""Health endpoints."""

from fastapi import APIRouter

from opendefence_core import __version__
from opendefence_core.config import get_core_config

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness and readiness probe"""
    return {"status": "ok"}


# TODO: Remove, for testing UI <-> API communication
@router.get("/healthcheck")
async def healthcheck() -> dict[str, str]:
    """Are we running at all"""
    config = get_core_config()
    return {"dns": config.domain, "version": __version__, "deployment": config.deployment}
