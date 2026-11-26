"""Traefik routes for the HTTP paths that an Integration lists."""

import re
from hashlib import sha256
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
Middleware = get_dynamic_resource("Middleware", "traefik.io/v1alpha1")

# Hostname prefix, shared middlewares, and TLS of each route host
_HOSTS: dict[str, tuple[str, tuple[str, ...], dict[str, Any]]] = {
    "Public": ("", (STRIP_IDENTITY_HEADERS_MIDDLEWARE, HSTS_MIDDLEWARE), {}),
    "App": (
        "app.",
        (STRIP_IDENTITY_HEADERS_MIDDLEWARE, PASS_CLIENT_CERT_MIDDLEWARE, HSTS_MIDDLEWARE),
        {"options": {"name": MTLS_TLS_OPTION, "namespace": TRAEFIK_NAMESPACE}},
    ),
}


# Top-level path prefixes that an integration may ask for. The UI serves every other top-level path.
REQUESTABLE_PREFIXES = ("/.well-known/", "/_")


def requestable(path: str) -> bool:
    """Whether an integration may ask for this path outside its own prefix. Replace this to use a deny list."""
    return path.startswith(REQUESTABLE_PREFIXES)


def covers(prefix: str, path: str) -> bool:
    """Whether the path is the prefix or is below it, by whole segments."""
    prefix = prefix.rstrip("/")
    return path.rstrip("/") == prefix or path.startswith(f"{prefix}/")


def owned_path(path: str) -> str:
    """The plain path that a route path is at or below. A regex gives its leading plain segments."""
    if not path.startswith("^"):
        return path
    plain = re.match(r"[A-Za-z0-9._~/-]*", path[1:])
    literal = plain.group() if plain else ""
    if path[1 + len(literal) :] in ("", "$"):
        return literal
    return literal[: literal.rfind("/")] or "/"


def _match(host: str, path: str) -> str:
    """Rule for the path and all below it. /a does not match /ab. A regex must also lie below its owned path."""
    owned = owned_path(path)
    paths = f"PathPrefix(`{owned}`)" if owned.endswith("/") else f"(Path(`{owned}`) || PathPrefix(`{owned}/`))"
    regex = f" && PathRegexp(`{path}`)" if path.startswith("^") else ""
    return f"Host(`{host}`) && {paths}{regex}"


def _strip_name(integration: Integration, prefix: str) -> str:
    """Name of the Middleware that strips this prefix. It stays the same when routes move."""
    return f"{integration.name}-strip-{sha256(prefix.encode()).hexdigest()[:8]}"


def route_resources(integration: Integration, domain: str) -> list[Unstructured]:
    """The Traefik objects for the Integration's routes, in its namespace: strip Middlewares, then IngressRoutes.

    Each distinct stripPrefix gets one Middleware. Each host that has routes gets one IngressRoute.
    """
    http_routes = integration.spec.network.ingress.http_routes
    resources = [
        Middleware.model_validate(
            {
                "metadata": {"name": _strip_name(integration, prefix), "namespace": integration.name},
                "spec": {"stripPrefix": {"prefixes": [prefix]}},
            }
        )
        for prefix in sorted({route.strip_prefix for route in http_routes if route.strip_prefix})
    ]
    for host, (prefix, middlewares, tls) in _HOSTS.items():
        rules = [
            {
                "kind": "Rule",
                "match": _match(prefix + domain, route.path),
                "middlewares": [
                    *({"name": name, "namespace": TRAEFIK_NAMESPACE} for name in middlewares),
                    *([{"name": _strip_name(integration, route.strip_prefix)}] if route.strip_prefix else []),
                ],
                "services": [{"name": route.service, "port": route.port}],
            }
            for route in http_routes
            if route.host == host
        ]
        if rules:
            resources.append(
                IngressRoute.model_validate(
                    {
                        "metadata": {"name": f"{integration.name}-{host.lower()}", "namespace": integration.name},
                        "spec": {"entryPoints": ["websecure"], "routes": rules, "tls": tls},
                    }
                )
            )
    return resources
