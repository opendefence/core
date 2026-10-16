"""Role controller: roles have no refs, so they resolve as soon as they exist."""

from cloudcoil.controller import Context, Controller

from lib_opendefence_core.models.v1alpha1 import Role
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved

roles = Controller(Role, name="roles", events=recorder("roles"))


@roles.reconcile()
async def reconcile_role(role: Role, ctx: Context[Role]) -> None:
    """Roles have no outgoing refs; mark them resolved."""
    mark_resolved(ctx)
