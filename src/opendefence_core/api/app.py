"""REST API for opendefence-core"""

from fastapi import FastAPI

from opendefence_core import __version__


# Traefik serves the API under /api and strips the prefix; root_path keeps the
# generated docs and OpenAPI URLs pointing at /api
app = FastAPI(title="opendefence-core", version=__version__, root_path="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness and readiness probe"""
    return {"status": "ok"}
