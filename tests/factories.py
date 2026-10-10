"""Builders for platform resources in tests."""

from collections.abc import Iterable
from datetime import datetime

from cloudcoil.apimachinery import ObjectMeta

from opendefence_core.models.v1alpha1 import (
    API_VERSION,
    REFERENCES_RESOLVED_CONDITION,
    SYNCED_CONDITION,
    Group,
    GroupSpec,
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
from opendefence_core.models.v1alpha1.common import PlatformCondition


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
    )


def make_user(
    name: str = "alpha1",
    *,
    namespace: str | None = None,
    roles: Iterable[str] = (),
    groups: Iterable[str] = (),
    approval_code: str | None = None,
    approved_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> User:
    """User whose callsign is its name, with uid uid-<name>."""
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=f"uid-{name}"),
        spec=UserSpec(
            callsign=name,
            role_refs=refs(roles),
            group_refs=refs(groups),
            approval_code=approval_code,
            approved_at=approved_at,
            revoked_at=revoked_at,
        ),
    )


def make_role(name: str) -> Role:
    """Role displayed by its name, with uid uid-<name>."""
    return Role(
        api_version=API_VERSION,
        kind="Role",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=RoleSpec(display_name=name),
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
        metadata=ObjectMeta(name=name, namespace=namespace, uid=f"uid-{namespace}-{name}"),
        spec=UserBindingSpec(user_ref=ObjectRef(name=user)),
        status=status,
    )
