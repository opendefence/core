"""Every route under /api/v3 has exactly the guard it is meant to have."""

from collections.abc import Callable

from fastapi.dependencies.models import Dependant
from fastapi.routing import iter_route_contexts

from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user, mtls_user, superadmin_user

GUARDS = {jwt_user, mtls_user, superadmin_user}
PUBLIC = {("GET", "/api/v3/health"), ("POST", "/api/v3/enrollment/check"), ("POST", "/api/v3/enrollment")}
JWT = {("GET", "/api/v3/enrollment"), ("POST", "/api/v3/certificates/csr"), ("GET", "/api/v3/certificates/chain.pem")}


def _calls(dependant: Dependant) -> set[Callable[..., object]]:
    found: set[Callable[..., object]] = set()
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            found.add(dependency.call)
        found |= _calls(dependency)
    return found


def _expected(method: str, path: str) -> set[Callable[..., object]]:
    if (method, path) in PUBLIC:
        return set()
    if (method, path) in JWT:
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
