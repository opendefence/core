"""User controller: resolve role and group name refs, and issue the user's mTLS certificate."""

from collections.abc import Sequence

from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.controller import Context, Controller, ResourceKey
from cloudcoil.models.cert_manager.v1 import CertificateRequest

from lib_opendefence_core.models.v1alpha1 import (
    BINDINGS_SYNCED_CONDITION,
    BindingObservation,
    Group,
    Role,
    User,
    UserBinding,
    is_synced,
)
from lib_opendefence_core.models.v1alpha1.user import normalize_callsign
from opendefence_core.certificates import wants_certificate
from opendefence_core.k8s_operator.controllers._certificates import reconcile_certificate
from opendefence_core.k8s_operator.controllers._events import recorder
from opendefence_core.k8s_operator.controllers._refs import mark_resolved, referrers_of, resolve_refs

users = Controller(User, name="users", owns=(CertificateRequest,), events=recorder("users"))


@users.validate(operations=("CREATE", "UPDATE"))
async def validate_user_callsign(request: AdmissionRequest[User]) -> None:
    """Reject a callsign another user already holds, comparing without regard to case.

    Users are named independently of their callsign, so Kubernetes no longer keeps
    callsigns unique.
    """
    obj = request.resource
    if obj is None:
        return
    callsign = normalize_callsign(obj.spec.callsign)
    old = request.old_resource
    if old is not None and normalize_callsign(old.spec.callsign) == callsign:
        return  # Approve, revoke and role writes leave the callsign alone
    client = await request.client(User)
    async for other in await client.list():
        if other.name != obj.name and normalize_callsign(other.spec.callsign) == callsign:
            raise AdmissionDenied(
                f"Callsign {obj.spec.callsign} is taken by user {other.name}",
                reason="CallsignTaken",
            )


@users.validate(operations=("DELETE",))
async def validate_user_delete(request: AdmissionRequest[User]) -> None:
    """Reject User deletes while any UserBinding still names this user."""
    obj = request.old_resource
    name = (obj.name if obj is not None else None) or request.name
    if not name:
        return
    client = await request.client(UserBinding)
    holders: list[str] = []
    async for binding in await client.list(all_namespaces=True):
        if binding.spec.user_ref.name != name:
            continue
        namespace = binding.namespace or ""
        binding_name = binding.name or ""
        holders.append(f"{namespace}/{binding_name}")
    if not holders:
        return
    holders.sort()
    raise AdmissionDenied(
        f"User still has UserBindings: {', '.join(holders)}",
        reason="HasBindings",
    )


@users.reconcile()
async def reconcile_user(user: User, ctx: Context[User]) -> None:
    """Write resolved refs and observed UserBinding sync state."""
    observed, pending = observe_bindings(user, ctx.cached(UserBinding).list(all_namespaces=True))
    report_bindings_synced(ctx, observed, pending)
    ctx.set_status(bindings=observed)
    if not wants_certificate(user):
        await reconcile_certificate(user, ctx)
    roles = resolve_refs(ctx, Role, user.spec.role_refs)
    groups = resolve_refs(ctx, Group, user.spec.group_refs)
    mark_resolved(ctx)
    ctx.set_status(roles=roles, groups=groups)
    if wants_certificate(user):
        await reconcile_certificate(user, ctx)


def observe_bindings(user: User, bindings: Sequence[UserBinding]) -> tuple[list[BindingObservation], list[str]]:
    """Collect UserBindings for this user and the ones that are not yet synced."""
    observed: list[BindingObservation] = []
    pending: list[str] = []
    user_name = user.name
    for binding in bindings:
        if binding.spec.user_ref.name != user_name:
            continue
        metadata = binding.metadata
        name = binding.name
        namespace = binding.namespace
        uid = metadata.uid if metadata is not None else None
        if not name or not namespace or not uid:
            continue
        synced = is_synced(binding)
        observed.append(
            BindingObservation(name=name, namespace=namespace, uid=uid, synced=synced),
        )
        if not synced:
            pending.append(f"{namespace}/{name}")
    observed.sort(key=lambda item: (item.namespace, item.name))
    pending.sort()
    return observed, pending


def report_bindings_synced(
    ctx: Context[User],
    observed: Sequence[BindingObservation],
    pending: Sequence[str],
) -> None:
    """Record whether every observed UserBinding has finished synchronizing."""
    if pending:
        ctx.condition(
            BINDINGS_SYNCED_CONDITION,
            False,
            reason="Pending",
            message=f"UserBinding not synced: {', '.join(pending)}",
        )
        return
    reason = "NoBindings" if not observed else "Synced"
    ctx.condition(BINDINGS_SYNCED_CONDITION, True, reason=reason)


@users.watch(Role)
def role_changed(role: Role) -> list[ResourceKey]:
    """Requeue users that name this role."""
    # Initial lists queue every user; reverse lookups need synced caches.
    if not users.ready:
        return []
    return referrers_of(users.cached(User).list(), lambda obj: obj.spec.role_refs, role)


@users.watch(Group)
def group_changed(group: Group) -> list[ResourceKey]:
    """Requeue users that name this group."""
    if not users.ready:
        return []
    return referrers_of(users.cached(User).list(), lambda obj: obj.spec.group_refs, group)


@users.watch(UserBinding)
def userbinding_changed(binding: UserBinding) -> list[ResourceKey]:
    """Requeue the User named by this binding."""
    if not users.ready:
        return []
    name = binding.spec.user_ref.name
    return [ResourceKey(name)] if name else []
