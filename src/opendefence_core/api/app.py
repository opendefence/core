"""FastAPI application, served by `opendefence_core api run`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from opendefence_core import __version__
from opendefence_core.api.config import get_api_config
from opendefence_core.api.routes.certificates.views import router as certificates_router
from opendefence_core.api.routes.enrollment.views import router as enrollment_router
from opendefence_core.api.routes.groups.views import router as groups_router
from opendefence_core.api.routes.health.views import router as health_router
from opendefence_core.api.routes.invites.views import router as invites_router
from opendefence_core.api.routes.roles.views import router as roles_router
from opendefence_core.api.routes.users.views import router as users_router
from opendefence_core.config import get_core_config


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Fail at startup rather than on the first request when configuration is missing."""
    get_core_config()
    get_api_config()
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
v3.include_router(groups_router)
v3.include_router(health_router)
v3.include_router(invites_router)
v3.include_router(roles_router)
v3.include_router(users_router)
app.include_router(v3)
