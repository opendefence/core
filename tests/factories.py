"""Builders for platform resources in tests."""

from collections.abc import Iterable
from datetime import datetime
from uuid import NAMESPACE_DNS, uuid5

from cloudcoil.apimachinery import ObjectMeta, OwnerReference

from lib_opendefence_core.models.v1alpha1 import (
    API_VERSION,
    REFERENCES_RESOLVED_CONDITION,
    SYNCED_CONDITION,
    Group,
    GroupSpec,
    Integration,
    IntegrationRole,
    IntegrationSpec,
    Invite,
    InviteSpec,
    InviteStatus,
    ObjectRef,
    Role,
    RoleSpec,
    User,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
    UserSpec,
)
from lib_opendefence_core.models.v1alpha1.common import PlatformCondition


def refs(names: Iterable[str]) -> list[ObjectRef]:
    """Name refs to the given objects."""
    return [ObjectRef(name=name) for name in names]


def condition(condition_type: str, status: bool, reason: str) -> PlatformCondition:
    """A condition as a controller would report it."""
    return PlatformCondition(
        last_transition_time="2026-09-13T00:00:00Z",
        message="",
        reason=reason,
        status="True" if status else "False",
        type=condition_type,
        observed_generation=1,
    )


def make_user(
    name: str = "alpha1",
    *,
    namespace: str | None = None,
    roles: Iterable[str] = (),
    groups: Iterable[str] = (),
    approval_code: str | None = None,
    approved_at: datetime | None = None,
    certificate_approved_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> User:
    """User whose callsign is its name, with a stable UUID and resource version."""
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=str(uuid5(NAMESPACE_DNS, name)), resource_version="1"),
        spec=UserSpec(
            callsign=name,
            role_refs=refs(roles),
            group_refs=refs(groups),
            approval_code=approval_code,
            approved_at=approved_at,
            certificate_approved_at=certificate_approved_at,
            revoked_at=revoked_at,
        ),
    )


def make_role(name: str, *, owner: str | None = None) -> Role:
    """Role displayed by its name, with uid uid-<name>. owner names the controlling Integration."""
    metadata = ObjectMeta(name=name, uid=f"uid-{name}")
    if owner is not None:
        metadata.owner_references = [
            OwnerReference(
                api_version=API_VERSION,
                kind="Integration",
                name=owner,
                uid=f"uid-{owner}",
                controller=True,
            )
        ]
    return Role(
        api_version=API_VERSION,
        kind="Role",
        metadata=metadata,
        spec=RoleSpec(display_name=name),
    )


def make_integration(name: str, *, roles: Iterable[str] = ()) -> Integration:
    """Integration displayed by its name, with uid uid-<name>."""
    return Integration(
        api_version=API_VERSION,
        kind="Integration",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=IntegrationSpec(
            display_name=name,
            version="1.0.0",
            extra_roles=[IntegrationRole(name=role, display_name=role) for role in roles],
        ),
    )


def make_group(
    name: str,
    *,
    parent: str | None = None,
    managers: Iterable[str] = (),
    roles: Iterable[str] = (),
) -> Group:
    """Group displayed by its name, with uid uid-<name>."""
    return Group(
        api_version=API_VERSION,
        kind="Group",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=GroupSpec(
            display_name=name,
            parent_ref=ObjectRef(name=parent) if parent else None,
            manager_refs=refs(managers),
            role_refs=refs(roles),
        ),
    )


def make_invite(
    name: str = "invite",
    *,
    code: str = "CODE1234",
    groups: Iterable[str] = (),
    roles: Iterable[str] = (),
    use_count: int = -1,
    used: int = 0,
    valid_until: datetime | None = None,
    auto_approve: bool = False,
    resolved: bool | None = None,
) -> Invite:
    """Invite, with a ReferencesResolved condition unless resolved is None."""
    conditions = [] if resolved is None else [_resolved_condition(resolved)]
    return Invite(
        api_version=API_VERSION,
        kind="Invite",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=InviteSpec(
            code=code,
            group_refs=refs(groups),
            role_refs=refs(roles),
            use_count=use_count,
            valid_until=valid_until,
            auto_approve=auto_approve,
        ),
        status=InviteStatus(conditions=conditions, used=used),
    )


def _resolved_condition(resolved: bool) -> PlatformCondition:
    return condition(REFERENCES_RESOLVED_CONDITION, resolved, "Resolved" if resolved else "MissingReference")


def make_binding(name: str, *, user: str, namespace: str = "taky", synced: bool | None = None) -> UserBinding:
    """UserBinding, with a Synced condition unless synced is None."""
    status = None
    if synced is not None:
        status = UserBindingStatus(
            conditions=[condition(SYNCED_CONDITION, synced, "Provisioned" if synced else "Pending")]
        )
    return UserBinding(
        api_version=API_VERSION,
        kind="UserBinding",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=f"uid-{namespace}-{name}", generation=1),
        spec=UserBindingSpec(user_ref=ObjectRef(name=user)),
        status=status,
    )
