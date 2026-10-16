"""Integration controller: create extra roles and drop the ones no longer listed."""

from contextlib import suppress

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context, Controller
from cloudcoil.errors import ResourceNotFound

from lib_opendefence_core.models.v1alpha1 import Integration, Role, RoleSpec
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved

integrations = Controller(Integration, name="integrations", owns=(Role,), events=recorder("integrations"))


def _owned_by(role: Role, integration: Integration) -> bool:
    """Whether this Integration is the controlling owner of the Role."""
    metadata = role.metadata
    owner = integration.metadata
    if metadata is None or owner is None or not owner.uid:
        return False
    return any(
        ref.controller and ref.uid == owner.uid and ref.kind == "Integration" for ref in metadata.owner_references or []
    )


@integrations.reconcile()
async def reconcile_integration(integration: Integration, ctx: Context[Integration]) -> None:
    """Create a Role for each extra role and delete owned Roles the spec no longer lists."""
    wanted = {role.name for role in integration.spec.extra_roles}
    client = await ctx.client(Role)
    for existing in ctx.cached(Role).list():
        if (
            not existing.name
            or existing.name in wanted
            or not _owned_by(existing, integration)
            or not existing.metadata
            or not existing.metadata.uid
        ):
            continue
        with suppress(ResourceNotFound):
            await client.delete(existing.name, uid=existing.metadata.uid)
    for role in integration.spec.extra_roles:
        await ctx.ensure(
            Role(
                kind="Role",
                metadata=ObjectMeta(name=role.name),
                spec=RoleSpec(display_name=role.display_name),
            )
        )
    mark_resolved(ctx)
