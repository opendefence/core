"""Reference helpers, reconcile handlers, and watch mappers."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import Mock, PropertyMock

import pytest
from cloudcoil.controller import Context, Controller, ResourceKey, TerminalError, Wait
from cloudcoil.errors import ResourceConflict
from cloudcoil.resources import Resource

from lib_opendefence_core.models.v1alpha1 import (
    BINDINGS_SYNCED_CONDITION,
    REFERENCES_RESOLVED_CONDITION,
    Group,
    Integration,
    Invite,
    ObjectRef,
    Role,
    User,
    UserBinding,
    is_synced,
)
from opendefence_core.k8s_operator.controllers import groups, invites, users
from opendefence_core.k8s_operator.controllers._refs import referrers_of, resolve_refs
from opendefence_core.k8s_operator.controllers.groups import manager_changed, parent_group_changed, reconcile_group
from opendefence_core.k8s_operator.controllers.groups import role_changed as group_role_changed
from opendefence_core.k8s_operator.controllers.integrations import reconcile_integration
from opendefence_core.k8s_operator.controllers.invites import group_changed as invite_group_changed
from opendefence_core.k8s_operator.controllers.invites import reconcile_invite
from opendefence_core.k8s_operator.controllers.invites import role_changed as invite_role_changed
from opendefence_core.k8s_operator.controllers.roles import reconcile_role
from opendefence_core.k8s_operator.controllers.users import group_changed as user_group_changed
from opendefence_core.k8s_operator.controllers.users import reconcile_user, userbinding_changed
from opendefence_core.k8s_operator.controllers.users import role_changed as user_role_changed
from tests.factories import make_binding, make_group, make_integration, make_invite, make_role, make_user
from tests.fakes import FakeCache, FakeClient, FakeContext


async def test_reconcile_user_resolves_refs() -> None:
    """User status receives UIDs for named roles and groups."""
    ctx = FakeContext({Role: FakeCache([make_role("superadmin")]), Group: FakeCache([make_group("ops")])})
    await reconcile_user(make_user("alice", roles=["superadmin"], groups=["ops"]), cast(Context[User], ctx))
    assert ctx.status["roles"][0].uid == "uid-superadmin"
    assert ctx.status["groups"][0].uid == "uid-ops"
    assert ctx.status["bindings"] == []
    assert (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "") in ctx.conditions
    assert (BINDINGS_SYNCED_CONDITION, True, "NoBindings", "") in ctx.conditions


async def test_reconcile_user_waits_for_missing_role() -> None:
    """Missing role refs wait instead of failing."""
    ctx = FakeContext()
    with pytest.raises(Wait) as raised:
        await reconcile_user(make_user("alice", roles=["missing"]), cast(Context[User], ctx))
    assert raised.value.reason == "MissingReference"
    assert (REFERENCES_RESOLVED_CONDITION, False, "MissingReference") in [
        (name, status, reason) for name, status, reason, _message in ctx.conditions
    ]


async def test_reconcile_group_and_invite() -> None:
    """Group reports references while Invite validates its references."""
    parent = make_group("root")
    role = make_role("group-admin")
    ctx = FakeContext(
        {Group: FakeCache([parent]), User: FakeCache([make_user("alice")]), Role: FakeCache([role])},
    )
    group = make_group("ops", parent="root", managers=["alice"], roles=["group-admin"])
    await reconcile_group(group, cast(Context[Group], ctx))
    assert ctx.status["parent"].uid == "uid-root"
    manager = ctx.cached(User).get("alice")
    assert manager is not None and manager.metadata is not None
    assert ctx.status["managers"][0].uid == manager.metadata.uid
    assert ctx.status["roles"][0].uid == "uid-group-admin"

    invite_ctx = FakeContext({Group: FakeCache([parent]), Role: FakeCache([role])})
    invite = make_invite("onboarding", groups=["root"], roles=["group-admin"])
    await reconcile_invite(invite, cast(Context[Invite], invite_ctx))
    assert invite_ctx.status == {}
    assert invite_ctx.conditions[-1] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "")


async def test_reconcile_group_rejects_self_parent() -> None:
    """A group may not name itself as parent."""
    ctx = FakeContext()
    with pytest.raises(TerminalError):
        await reconcile_group(make_group("ops", parent="ops"), cast(Context[Group], ctx))
    assert ctx.conditions[0][2] == "SelfReference"


async def test_reconcile_group_rejects_parent_cycle() -> None:
    """A two-node parent loop is a permanent reconcile failure."""
    ctx = FakeContext({Group: FakeCache([make_group("eng", parent="ops")])})
    with pytest.raises(TerminalError):
        await reconcile_group(make_group("ops", parent="eng"), cast(Context[Group], ctx))
    assert ctx.conditions[0][2] == "CycleDetected"
    assert "ops -> eng -> ops" in ctx.conditions[0][3]


async def test_reconcile_group_waits_for_missing_ancestor() -> None:
    """A missing ancestor waits instead of resolving the immediate parent."""
    ctx = FakeContext({Group: FakeCache([make_group("eng", parent="missing")])})
    with pytest.raises(Wait) as raised:
        await reconcile_group(make_group("ops", parent="eng"), cast(Context[Group], ctx))
    assert raised.value.reason == "MissingReference"
    assert ctx.conditions[0][2] == "MissingReference"


async def test_reconcile_integration_syncs_extra_roles() -> None:
    """Extra roles are created, dropped owned Roles are deleted, and other Roles stay."""
    owned = make_role("old-role", owner="tak")
    other = make_role("superadmin")
    client = FakeClient([owned, other])
    ctx = FakeContext({Role: FakeCache([owned, other])}, {Role: client})
    await reconcile_integration(make_integration("tak", roles=["mission-lead"]), cast(Context[Integration], ctx))
    assert [role.name for role in ctx.ensured] == ["mission-lead"]
    assert cast(Role, ctx.ensured[0]).spec.display_name == "mission-lead"
    assert client.deleted == [(None, "old-role")]
    assert ctx.conditions[-1][:3] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved")


async def test_integration_does_not_delete_replaced_role() -> None:
    """A stale cache cannot delete a new Role owned by another Integration."""
    cached = make_role("old-role", owner="tak")
    replacement = make_role("old-role", owner="radio")
    assert replacement.metadata is not None
    replacement.metadata.uid = "replacement-uid"
    client = FakeClient([replacement])
    ctx = FakeContext({Role: FakeCache([cached])}, clients={Role: client})
    with pytest.raises(ResourceConflict):
        await reconcile_integration(make_integration("tak"), cast(Context[Integration], ctx))
    assert client.deleted == []


def test_stale_binding_condition_does_not_acknowledge_new_spec() -> None:
    binding = make_binding("binding", user="alice", synced=True)
    assert binding.metadata is not None and binding.status is not None
    binding.metadata.generation = 2
    binding.spec.user_ref.name = "bobby"
    assert not is_synced(binding)
    binding.status.conditions[0].observed_generation = None
    assert not is_synced(binding)
    binding.status.conditions[0].observed_generation = 2
    assert is_synced(binding)
    binding.metadata.generation = None
    assert not is_synced(binding)


async def test_reconcile_role_marks_resolved() -> None:
    """Roles have no outgoing refs and report ReferencesResolved."""
    ctx = FakeContext()
    await reconcile_role(make_role("superadmin"), cast(Context[Role], ctx))
    assert ctx.conditions[-1] == (REFERENCES_RESOLVED_CONDITION, True, "Resolved", "")


def test_referrers_of_matches_name_refs() -> None:
    """Reverse mapping finds objects that name the target."""
    alice = make_user("alice", roles=["superadmin"])
    bob = make_user("bob", roles=["group-admin"])
    keys = referrers_of([alice, bob], lambda user: user.spec.role_refs, make_role("superadmin"))
    assert keys == [ResourceKey("alice")]


@pytest.mark.parametrize(
    ("controller", "mapper", "primary", "target"),
    [
        (groups, parent_group_changed, make_group("dependent", parent="target"), make_group("target")),
        (groups, manager_changed, make_group("dependent", managers=["target"]), make_user("target")),
        (groups, group_role_changed, make_group("dependent", roles=["target"]), make_role("target")),
        (users, user_group_changed, make_user("dependent", groups=["target"]), make_group("target")),
        (users, user_role_changed, make_user("dependent", roles=["target"]), make_role("target")),
        (invites, invite_group_changed, make_invite("dependent", groups=["target"]), make_group("target")),
        (invites, invite_role_changed, make_invite("dependent", roles=["target"]), make_role("target")),
    ],
)
def test_watch_mappers_wait_for_initial_sync(
    monkeypatch: pytest.MonkeyPatch,
    controller: Controller[Any],
    mapper: Callable[[Any], list[ResourceKey]],
    primary: Resource,
    target: Resource,
) -> None:
    """Initial list events must not read unsynced snapshots; later events requeue dependents."""
    ready = PropertyMock(return_value=False)
    monkeypatch.setattr(Controller, "ready", ready)
    cache = Mock()
    cache.list.return_value = [primary]
    cached = Mock(return_value=cache)
    monkeypatch.setattr(controller, "cached", cached)

    assert mapper(target) == []
    cached.assert_not_called()

    ready.return_value = True
    assert mapper(target) == [ResourceKey("dependent")]
    cached.assert_called_once_with(type(primary))

    cache.list.side_effect = RuntimeError("Informer watch failed")
    with pytest.raises(RuntimeError, match="Informer watch failed"):
        mapper(target)


def test_resolve_refs_skips_objects_without_uid() -> None:
    """A cached object without a UID is treated as missing."""
    role = make_role("superadmin")
    assert role.metadata is not None
    role.metadata.uid = None
    ctx = FakeContext({Role: FakeCache([role])})
    with pytest.raises(Wait):
        resolve_refs(ctx, Role, [ObjectRef(name="superadmin")])


async def test_reconcile_user_reports_pending_and_synced_bindings() -> None:
    """User status lists UserBindings and BindingsSynced follows the Synced condition."""
    pending = make_binding("bob", user="alice", namespace="taky", synced=False)
    synced = make_binding("alice", user="alice", namespace="radio", synced=True)
    other = make_binding("bob", user="bob", namespace="radio", synced=True)
    ctx = FakeContext({UserBinding: FakeCache([pending, synced, other])})
    await reconcile_user(make_user("alice"), cast(Context[User], ctx))
    bindings = ctx.status["bindings"]
    assert [(item.namespace, item.name, item.synced) for item in bindings] == [
        ("radio", "alice", True),
        ("taky", "bob", False),
    ]
    assert (BINDINGS_SYNCED_CONDITION, False, "Pending", "UserBinding not synced: taky/bob") in ctx.conditions

    synced_only = FakeContext({UserBinding: FakeCache([synced])})
    await reconcile_user(make_user("alice"), cast(Context[User], synced_only))
    assert synced_only.status["bindings"][0].synced is True
    assert (BINDINGS_SYNCED_CONDITION, True, "Synced", "") in synced_only.conditions


def test_is_synced_reads_synced_condition() -> None:
    """UserBinding synchronization is True only when the Synced condition is True."""
    assert is_synced(make_binding("bob", user="bob")) is False
    assert is_synced(make_binding("bob", user="bob", synced=False)) is False
    assert is_synced(make_binding("bob", user="bob", synced=True)) is True


def test_userbinding_changed_requeues_named_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """UserBinding events requeue the cluster-scoped User named in userRef."""
    ready = PropertyMock(return_value=False)
    monkeypatch.setattr(Controller, "ready", ready)
    binding = make_binding("bob", user="alice", namespace="taky")
    assert userbinding_changed(binding) == []

    ready.return_value = True
    assert userbinding_changed(binding) == [ResourceKey("alice")]
