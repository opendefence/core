"""Role controller: roles have no refs, so they resolve as soon as they exist."""

from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.controller import Context, Controller

from lib_opendefence_core.models.v1alpha1 import Group, Invite, Role, User
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved, named_by

roles = Controller(Role, name="roles", events=recorder("roles"))


@roles.validate(operations=("DELETE",))
async def validate_role_delete(request: AdmissionRequest[Role]) -> None:
    """Reject Role deletes while a User, Group, or Invite names this role in roleRefs."""
    name = request.name
    if not name:
        return
    role = request.old_resource
    owners = role.metadata.owner_references if role is not None and role.metadata else None
    if any(ref.kind == "Integration" and ref.controller for ref in owners or []):
        return  # Removing an Integration must remove its Roles
    holders = [
        *await named_by(request, User, lambda obj: obj.spec.role_refs, name),
        *await named_by(request, Group, lambda obj: obj.spec.role_refs, name),
        *await named_by(request, Invite, lambda obj: obj.spec.role_refs, name),
    ]
    if holders:
        raise AdmissionDenied(f"Role is still named by: {', '.join(sorted(holders))}", reason="StillReferenced")


@roles.reconcile()
async def reconcile_role(role: Role, ctx: Context[Role]) -> None:
    """Roles have no outgoing refs; mark them resolved."""
    mark_resolved(ctx)
