"""Health endpoints."""

from fastapi import APIRouter, HTTPException, status

from opendefence_core.api.lib.jwt import load_key
from opendefence_core.api.routes.health.schema import HealthResponse
from opendefence_core.config import get_core_config

router = APIRouter(tags=["health"])
probes = APIRouter(tags=["health"], include_in_schema=False)


@probes.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@probes.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe."""
    try:
        load_key()
    except (OSError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/health")
async def health() -> HealthResponse:
    """The deployment that answered."""
    config = get_core_config()
    return HealthResponse(status="ok", deployment=config.deployment, domain=config.domain)
