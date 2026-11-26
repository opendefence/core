"""Integration controller: write extra roles and routes, and delete the ones no longer listed."""

from contextlib import suppress

from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context, Controller
from cloudcoil.errors import ResourceNotFound
from cloudcoil.resources import Resource

from lib_opendefence_core.models.v1alpha1 import Integration, Role, RoleSpec
from opendefence_core.config import get_core_config
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved
from opendefence_core.k8s_operator.controllers._routes import (
    IngressRoute,
    Middleware,
    covers,
    requestable,
    route_resources,
)

integrations = Controller(
    Integration, name="integrations", owns=(Role, IngressRoute, Middleware), events=recorder("integrations")
)


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
    requested = [route for route in routes if not covers(f"/integrations/{obj.name}", route.path)]
    for route in requested:
        if covers("/integrations", route.path) or not requestable(route.path):
            raise AdmissionDenied(f"Path {route.path} is reserved", reason="PathReserved")
    if not requested:
        return
    client = await request.client(Integration)
    async for other in await client.list():
        if other.name == obj.name:
            continue
        for taken in other.spec.network.ingress.http_routes:
            for route in requested:
                if route.host == taken.host and (covers(taken.path, route.path) or covers(route.path, taken.path)):
                    raise AdmissionDenied(
                        f"Path {route.path} on the {route.host} host is taken by integration {other.name}",
                        reason="PathTaken",
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


@integrations.reconcile()
async def reconcile_integration(integration: Integration, ctx: Context[Integration]) -> None:
    """Write the Integration's extra Roles and routes, and delete the owned ones that the spec no longer lists."""
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
    mark_resolved(ctx)
