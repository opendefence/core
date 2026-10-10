"""Group controller: resolve parent, manager, and role name refs into status."""

from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.controller import Context, Controller, ResourceKey
from cloudcoil.errors import ResourceNotFound

from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import (
    inspect_parent_chain,
    mark_resolved,
    referrers_of,
    reject_parent_chain_issue,
    resolve_optional_ref,
    resolve_refs,
)
from opendefence_core.k8s_operator.models.v1alpha1 import Group, Role, User

groups = Controller(Group, name="groups", events=recorder("groups"))


def _parent_of(group: Group) -> str | None:
    """Return the parent group name, if declared."""
    ref = group.spec.parent_ref
    return None if ref is None else ref.name


@groups.validate(operations=("CREATE", "UPDATE", "DELETE"))
async def validate_group(request: AdmissionRequest[Group]) -> None:
    """Reject Group writes that self-parent, cycle, name a missing ancestor, or delete a parent."""
    if request.operation == "DELETE":
        await _deny_delete_with_children(request)
        return
    obj = request.resource
    if obj is None:
        return
    parent = _parent_of(obj)
    if parent is None:
        return
    client = await request.client(Group)

    async def get(name: str) -> Group | None:
        try:
            return await client.get(name)
        except ResourceNotFound:
            return None

    issue = await inspect_parent_chain(obj.name, parent, get, _parent_of)
    if issue is not None:
        raise AdmissionDenied(issue.message, reason=issue.reason)


async def _deny_delete_with_children(request: AdmissionRequest[Group]) -> None:
    """Reject DELETE when any other group still names this group as parent."""
    obj = request.old_resource
    name = (obj.name if obj is not None else None) or request.name
    if not name:
        return
    client = await request.client(Group)
    children: list[str] = []
    async for group in await client.list():
        if group.name and _parent_of(group) == name:
            children.append(group.name)
    if not children:
        return
    children.sort()
    raise AdmissionDenied(
        f"Group still has child groups: {', '.join(children)}",
        reason="HasChildren",
    )


@groups.reconcile()
async def reconcile_group(group: Group, ctx: Context[Group]) -> None:
    """Write resolved parent, manager, and role UIDs, waiting for missing targets."""

    async def get(name: str) -> Group | None:
        return ctx.cached(Group).get(name)

    issue = await inspect_parent_chain(group.name, _parent_of(group), get, _parent_of)
    if issue is not None:
        reject_parent_chain_issue(ctx, issue)
    parent = resolve_optional_ref(ctx, Group, group.spec.parent_ref)
    managers = resolve_refs(ctx, User, group.spec.manager_refs)
    roles = resolve_refs(ctx, Role, group.spec.role_refs)
    mark_resolved(ctx)
    ctx.set_status(parent=parent, managers=managers, roles=roles)


@groups.watch(Group)
def parent_group_changed(group: Group) -> list[ResourceKey]:
    """Requeue groups that name this group as parent."""
    # Initial lists already enqueue every primary; pooled watches can fire
    # before the primary cache is synced, so defer reverse lookups until ready.
    if not groups.ready:
        return []
    return referrers_of(groups.cached(Group).list(), lambda obj: obj.spec.parent_ref, group)


@groups.watch(User)
def manager_changed(user: User) -> list[ResourceKey]:
    """Requeue groups that name this user as a manager."""
    if not groups.ready:
        return []
    return referrers_of(groups.cached(Group).list(), lambda obj: obj.spec.manager_refs, user)


@groups.watch(Role)
def role_changed(role: Role) -> list[ResourceKey]:
    """Requeue groups that name this role."""
    if not groups.ready:
        return []
    return referrers_of(groups.cached(Group).list(), lambda obj: obj.spec.role_refs, role)
