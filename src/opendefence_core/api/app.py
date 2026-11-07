"""FastAPI application, served by `opendefence_core api run`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from opendefence_core import __version__
from opendefence_core.api.config import get_api_config
from opendefence_core.api.routes.certificates.views import router as certificates_router
from opendefence_core.api.routes.enrollment.views import router as enrollment_router
from opendefence_core.api.routes.groups.views import router as groups_router
from opendefence_core.api.routes.health.views import probes as probes_router
from opendefence_core.api.routes.health.views import router as health_router
from opendefence_core.api.routes.integrations.views import router as integrations_router
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
    docs_url=None,
    openapi_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

v3 = APIRouter(prefix="/api/v3")
v3.include_router(certificates_router)
v3.include_router(enrollment_router)
v3.include_router(groups_router)
v3.include_router(health_router)
v3.include_router(integrations_router)
v3.include_router(invites_router)
v3.include_router(roles_router)
v3.include_router(users_router)
app.include_router(v3)

# Outside /api, so Traefik never serves them
app.include_router(probes_router)

# The routes Traefik serves on <domain>; everything else is only on app.<domain>
PUBLIC_ROUTES = {("GET", "/api/v3/health"), ("POST", "/api/v3/enrollment/check"), ("POST", "/api/v3/enrollment")}
JWT_ROUTES = {
    ("GET", "/api/v3/enrollment"),
    ("POST", "/api/v3/certificates/csr"),
    ("GET", "/api/v3/certificates/chain.pem"),
}


@app.get("/api/openapi.json", include_in_schema=False)
async def openapi(request: Request) -> JSONResponse:
    """The OpenAPI document; on <domain>, only the routes served there."""
    schema = app.openapi()
    if request.url.hostname != get_core_config().domain:
        return JSONResponse(schema)
    served = PUBLIC_ROUTES | JWT_ROUTES
    paths = {
        path: kept
        for path, operations in schema["paths"].items()
        if (kept := {method: op for method, op in operations.items() if (method.upper(), path) in served})
    }
    return JSONResponse({**schema, "paths": paths})


@app.get("/api/docs", include_in_schema=False)
async def docs() -> HTMLResponse:
    """Swagger UI for the OpenAPI document of the requested host."""
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title=app.title)
