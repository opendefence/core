"""Integration controller: write extra roles, routes and port Services, and delete the ones no longer listed."""

import re
from contextlib import suppress

from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context, Controller, ResourceKey, Wait
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.kubernetes.core.v1 import Service
from cloudcoil.resources import Resource

from lib_opendefence_core.models.v1alpha1 import PORTS_READY_CONDITION, Integration, Role, RoleSpec
from lib_opendefence_core.models.v1alpha1.integration import IntegrationHttpRoute
from opendefence_core.config import get_core_config
from opendefence_core.k8s_operator.config import get_operator_config
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._ports import port_services, public_ports
from opendefence_core.k8s_operator.controllers._refs import mark_resolved
from opendefence_core.k8s_operator.controllers._routes import (
    IngressRoute,
    Middleware,
    covers,
    owned_path,
    requestable,
    route_resources,
)

integrations = Controller(
    Integration, name="integrations", owns=(Role, IngressRoute, Middleware, Service), events=recorder("integrations")
)


def _check_route(route: IntegrationHttpRoute) -> None:
    """Reject a path that is not a regular expression, and a blocked path that is not below its route."""
    try:
        re.compile(route.path if route.path.startswith("^") else "")
    except re.error as error:
        raise AdmissionDenied(f"Path {route.path} is not a regular expression", reason="InvalidPathRegex") from error
    for blocked in route.blocked_paths:
        if not covers(owned_path(route.path), blocked):
            raise AdmissionDenied(f"Blocked path {blocked} is not below {route.path}", reason="PathReserved")


@integrations.validate(operations=("CREATE", "UPDATE"))
async def validate_integration_paths(request: AdmissionRequest[Integration]) -> None:
    """Reject a route path that is reserved, or that overlaps a path of another Integration on the same host.

    Paths below /integrations/<name> belong to the Integration. Other paths must be requestable.
    """
    obj = request.resource
    if obj is None:
        return
    routes = obj.spec.network.ingress.http_routes
    old = request.old_resource
    if old is not None and old.spec.network.ingress.http_routes == routes:
        return  # Other writes leave the routes alone
    for route in routes:
        _check_route(route)
    requested = [route for route in routes if not covers(f"/integrations/{obj.name}", owned_path(route.path))]
    for route in requested:
        if covers("/integrations", owned_path(route.path)) or not requestable(owned_path(route.path)):
            raise AdmissionDenied(f"Path {route.path} is reserved", reason="PathReserved")
    if not requested:
        return
    client = await request.client(Integration)
    async for other in await client.list():
        if other.name == obj.name:
            continue
        for taken in other.spec.network.ingress.http_routes:
            for route in requested:
                mine, theirs = owned_path(route.path), owned_path(taken.path)
                if route.host == taken.host and (covers(theirs, mine) or covers(mine, theirs)):
                    raise AdmissionDenied(
                        f"Path {route.path} on the {route.host} host is taken by integration {other.name}",
                        reason="PathTaken",
                    )


@integrations.validate(operations=("CREATE", "UPDATE"))
async def validate_integration_ports(request: AdmissionRequest[Integration]) -> None:
    """Reject a publicPort that is listed twice, or that another Integration sets or holds from the pool."""
    obj = request.resource
    if obj is None:
        return
    ports = obj.spec.network.ingress.ports
    old = request.old_resource
    if old is not None and old.spec.network.ingress.ports == ports:
        return  # Other writes leave the ports alone
    pinned = [(port.protocol, port.public_port) for port in ports if port.public_port is not None]
    for protocol, number in pinned:
        if pinned.count((protocol, number)) > 1:
            raise AdmissionDenied(f"{protocol} port {number} is listed twice", reason="PortTaken")
    if not pinned:
        return
    client = await request.client(Integration)
    async for other in await client.list():
        if other.name == obj.name:
            continue
        held = other.status.ports if other.status else []
        for taken in [*other.spec.network.ingress.ports, *held]:
            if (taken.protocol, taken.public_port) in pinned:
                raise AdmissionDenied(
                    f"{taken.protocol} port {taken.public_port} is taken by integration {other.name}",
                    reason="PortTaken",
                )


def _owned_by(resource: Resource, integration: Integration) -> bool:
    """Whether this Integration is the controlling owner of the resource."""
    metadata = resource.metadata
    owner = integration.metadata
    if metadata is None or owner is None or not owner.uid:
        return False
    return any(
        ref.controller and ref.uid == owner.uid and ref.kind == "Integration" for ref in metadata.owner_references or []
    )


async def _delete_unwanted(
    ctx: Context[Integration], kind: type[Resource], integration: Integration, wanted: set[str | None]
) -> None:
    """Delete the resources of this kind that the Integration owns and no longer lists."""
    client = await ctx.client(kind)
    for existing in ctx.cached(kind).list(all_namespaces=True):
        if (
            not existing.name
            or existing.name in wanted
            or not _owned_by(existing, integration)
            or not existing.metadata
            or not existing.metadata.uid
        ):
            continue
        with suppress(ResourceNotFound):
            await client.delete(existing.name, existing.namespace, uid=existing.metadata.uid)


async def _open_ports(integration: Integration, ctx: Context[Integration]) -> None:
    """Write the Services for the Integration's public ports, and report the ports and the result in status."""
    ports = integration.spec.network.ingress.ports
    taken: set[int] = set()
    if any(port.public_port is None for port in ports):
        client = await ctx.client(Integration)
        async for other in await client.list():
            if other.name != integration.name and other.status:
                taken.update(port.public_port for port in other.status.ports)
    config = get_operator_config()
    public = public_ports(integration, taken, config.port_pool)
    ctx.set_status(ports=public)
    services, missing = port_services(integration, public, ctx.cached(Service), config.port_service_type)
    # A dropped Service goes first, because it can hold a port that another Service now needs
    await _delete_unwanted(ctx, Service, integration, {service.name for service in services})
    for service in services:
        await ctx.ensure(service)
    unassigned = sorted({port.name for port in ports} - {port.name for port in public})
    if unassigned:
        message = f"The pool has no free port for: {', '.join(unassigned)}"
        ctx.condition(PORTS_READY_CONDITION, False, reason="PoolExhausted", message=message)
        raise Wait("PoolExhausted", message, after=60)
    if missing:
        message = f"No backend Service port for: {', '.join(missing)}"
        ctx.condition(PORTS_READY_CONDITION, False, reason="BackendNotFound", message=message)
        raise Wait("BackendNotFound", message, after=60)
    ctx.condition(PORTS_READY_CONDITION, True, reason="Opened")


@integrations.reconcile()
async def reconcile_integration(integration: Integration, ctx: Context[Integration]) -> None:
    """Write the Integration's extra Roles, routes and ports, and delete the owned ones that the spec no longer lists."""
    await _delete_unwanted(ctx, Role, integration, {role.name for role in integration.spec.extra_roles})
    for role in integration.spec.extra_roles:
        await ctx.ensure(
            Role(
                kind="Role",
                metadata=ObjectMeta(name=role.name),
                spec=RoleSpec(display_name=role.display_name),
            )
        )
    resources = route_resources(integration, get_core_config().domain)
    for resource in resources:
        await ctx.ensure(resource)
    # Routes go before the Middlewares that they name
    for kind in (IngressRoute, Middleware):
        await _delete_unwanted(ctx, kind, integration, {item.name for item in resources if isinstance(item, kind)})
    await _open_ports(integration, ctx)
    mark_resolved(ctx)


@integrations.watch(Service)
def backend_changed(service: Service) -> list[ResourceKey]:
    """Requeue the Integration of the Service's namespace when one of its ports names the Service."""
    # Initial lists queue every Integration; reverse lookups need synced caches.
    if not integrations.ready or not service.namespace:
        return []
    integration = integrations.cached(Integration).get(service.namespace)
    if integration and any(port.service == service.name for port in integration.spec.network.ingress.ports):
        return [ResourceKey(service.namespace)]
    return []
