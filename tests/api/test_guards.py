"""Every route under /api/v3 has exactly the guard it is meant to have."""

import re
from collections.abc import Callable
from pathlib import Path

from fastapi.dependencies.models import Dependant
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from opendefence_core.api.app import JWT_ROUTES, PUBLIC_ROUTES, app
from opendefence_core.api.dependencies import jwt_user, mtls_user, superadmin_user

GUARDS = {jwt_user, mtls_user, superadmin_user}
MAIN_DOMAIN_ROUTE = Path(__file__).resolve().parents[2] / "manifests" / "ingress" / "api.yaml"


def _calls(dependant: Dependant) -> set[Callable[..., object]]:
    found: set[Callable[..., object]] = set()
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            found.add(dependency.call)
        found |= _calls(dependency)
    return found


def _expected(method: str, path: str) -> set[Callable[..., object]]:
    if (method, path) in PUBLIC_ROUTES:
        return set()
    if (method, path) in JWT_ROUTES:
        return {jwt_user}
    if path == "/api/v3/users/me" or path.startswith("/api/v3/integrations"):
        return {mtls_user}
    return {superadmin_user, mtls_user}


def test_every_route_has_its_guard() -> None:
    """Public routes have no guard, JWT routes only the JWT, and the rest the certificate or superadmin."""
    routes = [(r.path, r) for r in iter_route_contexts(app.routes) if r.path and r.path.startswith("/api/v3")]
    assert routes
    for path, route in routes:
        guards = _calls(route.dependant) & GUARDS
        for method in route.methods or ():
            assert guards == _expected(method, path), f"{method} {path}"


def test_main_domain_serves_only_public_and_jwt_routes() -> None:
    """The <domain> IngressRoute lists exactly the public and JWT paths, plus the API docs."""
    served = set(re.findall(r"Path(?:Prefix|Regexp)?\(`([^`]+)`\)", MAIN_DOMAIN_ROUTE.read_text()))
    assert served == {path for _, path in PUBLIC_ROUTES | JWT_ROUTES} | {"/api/docs", "/api/openapi.json"}


def test_docs_on_the_main_domain_list_only_its_routes() -> None:
    """<domain> documents only the routes Traefik serves there; other hosts document every route."""
    client = TestClient(app)
    main = client.get("/api/openapi.json", headers={"host": "local-dev.opendefence.fi"}).json()["paths"]
    documented = {(method.upper(), path) for path, operations in main.items() for method in operations}
    assert documented == PUBLIC_ROUTES | JWT_ROUTES
    assert (
        "/api/v3/groups"
        in client.get("/api/openapi.json", headers={"host": "app.local-dev.opendefence.fi"}).json()["paths"]
    )
    assert client.get("/api/docs").status_code == 200
