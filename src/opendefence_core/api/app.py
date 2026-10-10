"""FastAPI application, run with `uvicorn opendefence_core.api.app:app`"""

from fastapi import APIRouter, FastAPI

from opendefence_core import __version__
from opendefence_core.api.routes.certificates.views import router as certificates_router
from opendefence_core.api.routes.enrollment.views import router as enrollment_router
from opendefence_core.api.routes.health.views import router as health_router


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
v3.include_router(health_router)
app.include_router(v3)
