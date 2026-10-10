"""Invite controller: validate group and role name references."""

from cloudcoil.controller import Context, Controller, ResourceKey

from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved, referrers_of, resolve_refs
from opendefence_core.k8s_operator.models.v1alpha1 import Group, Invite, Role

invites = Controller(Invite, name="invites", events=recorder("invites"))


@invites.reconcile()
async def reconcile_invite(invite: Invite, ctx: Context[Invite]) -> None:
    """Validate references, waiting for missing targets."""
    resolve_refs(ctx, Group, invite.spec.group_refs)
    resolve_refs(ctx, Role, invite.spec.role_refs)
    mark_resolved(ctx)


@invites.watch(Group)
def group_changed(group: Group) -> list[ResourceKey]:
    """Requeue invites that name this group."""
    # Initial lists queue every invite; reverse lookups need synced caches.
    if not invites.ready:
        return []
    return referrers_of(invites.cached(Invite).list(), lambda obj: obj.spec.group_refs, group)


@invites.watch(Role)
def role_changed(role: Role) -> list[ResourceKey]:
    """Requeue invites that name this role."""
    if not invites.ready:
        return []
    return referrers_of(invites.cached(Invite).list(), lambda obj: obj.spec.role_refs, role)
