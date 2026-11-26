"""Traefik routes for the HTTP paths that an Integration lists."""

from typing import Any

from cloudcoil.resources import Unstructured, get_dynamic_resource

from lib_opendefence_core.models.v1alpha1 import Integration
from opendefence_core.naming import (
    HSTS_MIDDLEWARE,
    MTLS_TLS_OPTION,
    PASS_CLIENT_CERT_MIDDLEWARE,
    STRIP_IDENTITY_HEADERS_MIDDLEWARE,
    TRAEFIK_NAMESPACE,
)

IngressRoute = get_dynamic_resource("IngressRoute", "traefik.io/v1alpha1")

# Hostname prefix, shared middlewares, and TLS of each route host
_HOSTS: dict[str, tuple[str, tuple[str, ...], dict[str, Any]]] = {
    "Public": ("", (STRIP_IDENTITY_HEADERS_MIDDLEWARE, HSTS_MIDDLEWARE), {}),
    "App": (
        "app.",
        (STRIP_IDENTITY_HEADERS_MIDDLEWARE, PASS_CLIENT_CERT_MIDDLEWARE, HSTS_MIDDLEWARE),
        {"options": {"name": MTLS_TLS_OPTION, "namespace": TRAEFIK_NAMESPACE}},
    ),
}


def _match(host: str, path: str) -> str:
    """Rule for the path and all below it. /a does not match /ab."""
    paths = f"PathPrefix(`{path}`)" if path.endswith("/") else f"(Path(`{path}`) || PathPrefix(`{path}/`))"
    return f"Host(`{host}`) && {paths}"


def ingress_routes(integration: Integration, domain: str) -> list[Unstructured]:
    """One IngressRoute in the Integration's namespace for each host that it lists routes on."""
    routes = []
    for host, (prefix, middlewares, tls) in _HOSTS.items():
        rules = [
            {
                "kind": "Rule",
                "match": _match(prefix + domain, route.path),
                "middlewares": [{"name": name, "namespace": TRAEFIK_NAMESPACE} for name in middlewares],
                "services": [{"name": route.service, "port": route.port}],
            }
            for route in integration.spec.network.ingress.http_routes
            if route.host == host
        ]
        if rules:
            routes.append(
                IngressRoute.model_validate(
                    {
                        "metadata": {"name": f"{integration.name}-{host.lower()}", "namespace": integration.name},
                        "spec": {"entryPoints": ["websecure"], "routes": rules, "tls": tls},
                    }
                )
            )
    return routes
