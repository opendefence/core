"""Traefik routes for the HTTP paths that an Integration lists."""

from typing import Any

from cloudcoil.resources import Unstructured, get_dynamic_resource

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import IntegrationHttpRoute
from opendefence_core.naming import HSTS_MIDDLEWARE, STRIP_IDENTITY_HEADERS_MIDDLEWARE, TRAEFIK_NAMESPACE

IngressRoute = get_dynamic_resource("IngressRoute", "traefik.io/v1alpha1")


def _match(host: str, path: str) -> str:
    """Rule for the path and all below it. /a does not match /ab."""
    paths = f"PathPrefix(`{path}`)" if path.endswith("/") else f"(Path(`{path}`) || PathPrefix(`{path}/`))"
    return f"Host(`{host}`) && {paths}"


def _rule(host: str, route: IntegrationHttpRoute) -> dict[str, Any]:
    """Traefik rule that sends the route's path on this host to its Service."""
    return {
        "kind": "Rule",
        "match": _match(host, route.path),
        "middlewares": [
            {"name": STRIP_IDENTITY_HEADERS_MIDDLEWARE, "namespace": TRAEFIK_NAMESPACE},
            {"name": HSTS_MIDDLEWARE, "namespace": TRAEFIK_NAMESPACE},
        ],
        "services": [{"name": route.service, "port": route.port}],
    }


def public_route(integration: Integration, domain: str) -> Unstructured | None:
    """IngressRoute for the Public routes in the Integration's namespace, or None when it lists none."""
    rules = [_rule(domain, route) for route in integration.spec.network.ingress.http_routes if route.host == "Public"]
    if not rules:
        return None
    return IngressRoute.model_validate(
        {
            "metadata": {"name": f"{integration.name}-public", "namespace": integration.name},
            "spec": {"entryPoints": ["websecure"], "routes": rules, "tls": {}},
        }
    )
