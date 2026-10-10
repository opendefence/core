"""FastAPI application, run with `uvicorn opendefence_core.api.app:app`"""

from fastapi import APIRouter, FastAPI

from opendefence_core import __version__
from opendefence_core.api.config import config
from opendefence_core.api.routes.certificates.views import router as certificates_router
from opendefence_core.api.routes.enrollment.views import router as enrollment_router


app = FastAPI(
    title="opendefence-core",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

v3 = APIRouter(prefix="/api/v3")
v3.include_router(certificates_router)
v3.include_router(enrollment_router)
app.include_router(v3)


# TODO: Remove, for testing UI <-> API communication
@app.get("/api/v3/healthcheck")
async def healthcheck() -> dict[str, str]:
    """Are we running at all"""
    return {"dns": config.domain, "version": __version__, "deployment": config.deployment}


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness and readiness probe; Traefik only routes /api, so this stays in-cluster"""
    return {"status": "ok"}
