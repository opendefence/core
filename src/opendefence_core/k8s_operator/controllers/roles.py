"""Role controller: report Ready for catalog roles."""

from cloudcoil.controller import Context, Controller

from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved
from opendefence_core.k8s_operator.models.v1alpha1 import Role

roles = Controller(Role, name="roles", events=recorder("roles"))


@roles.reconcile()
async def reconcile_role(role: Role, ctx: Context[Role]) -> None:
    """Roles have no outgoing refs; mark them resolved."""
    mark_resolved(ctx)
