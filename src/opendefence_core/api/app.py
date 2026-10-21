"""FastAPI application, served by `opendefence_core api run`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from opendefence_core import __version__, config
from opendefence_core.api.config import get_config
from opendefence_core.api.routes.certificates.views import router as certificates_router
from opendefence_core.api.routes.enrollment.views import router as enrollment_router
from opendefence_core.api.routes.health.views import router as health_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Fail at startup rather than on the first request when configuration is missing."""
    config.get_config()
    get_config()
    yield


app = FastAPI(
    title="opendefence-core",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

v3 = APIRouter(prefix="/api/v3")
v3.include_router(certificates_router)
v3.include_router(enrollment_router)
v3.include_router(health_router)
app.include_router(v3)
