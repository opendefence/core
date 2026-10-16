"""Admission webhooks: Group parent chains and deletes, User callsigns and deletes."""

from typing import cast

import pytest
from cloudcoil.admission import AdmissionDenied, AdmissionRequest

from lib_opendefence_core.models.v1alpha1 import Group, User
from opendefence_core.k8s_operator.controllers.groups import validate_group
from opendefence_core.k8s_operator.controllers.users import validate_user_callsign, validate_user_delete
from tests.factories import make_binding, make_group, make_user
from tests.fakes import FakeAdmissionRequest


async def _validate_group(request: FakeAdmissionRequest[Group]) -> None:
    await validate_group(cast(AdmissionRequest[Group], request))


async def _validate_user_delete(request: FakeAdmissionRequest[User]) -> None:
    await validate_user_delete(cast(AdmissionRequest[User], request))


async def _validate_user_callsign(request: FakeAdmissionRequest[User]) -> None:
    await validate_user_callsign(cast(AdmissionRequest[User], request))


async def test_validate_group_allows_acyclic_parent() -> None:
    """A child may name an existing ancestor chain."""
    ancestors = [make_group("root"), make_group("engineering", parent="root")]
    await _validate_group(FakeAdmissionRequest(resource=make_group("ops", parent="engineering"), objects=ancestors))


async def test_validate_group_allows_missing_resource_snapshot() -> None:
    """DELETE-style requests with no object or name are ignored."""
    request = FakeAdmissionRequest[Group](operation="DELETE")
    await _validate_group(request)
    assert request.client_calls == 0


async def test_validate_group_allows_delete_without_children() -> None:
    """A leaf group may be deleted while its parent remains."""
    leaf = make_group("eng", parent="ops")
    await _validate_group(
        FakeAdmissionRequest(operation="DELETE", old_resource=leaf, objects=[make_group("ops"), leaf])
    )


async def test_validate_group_rejects_delete_with_children() -> None:
    """A group named as parentRef by another group cannot be deleted."""
    parent = make_group("ops")
    children = [make_group("eng", parent="ops"), make_group("platform", parent="ops")]
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(
            FakeAdmissionRequest(operation="DELETE", old_resource=parent, objects=[parent, *children])
        )
    assert raised.value.reason == "HasChildren"
    assert "eng, platform" in str(raised.value)


async def test_validate_group_allows_root_group_without_client() -> None:
    """Groups with no parentRef do not perform live reads."""
    request = FakeAdmissionRequest(resource=make_group("ops"))
    await _validate_group(request)
    assert request.client_calls == 0


async def test_validate_group_rejects_self_parent() -> None:
    """Direct self-parent is denied."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(FakeAdmissionRequest(resource=make_group("ops", parent="ops")))
    assert raised.value.reason == "SelfReference"
    assert "same object" in str(raised.value)


async def test_validate_group_rejects_two_node_cycle() -> None:
    """ops -> eng -> ops is denied."""
    request = FakeAdmissionRequest(resource=make_group("ops", parent="eng"), objects=[make_group("eng", parent="ops")])
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(request)
    assert raised.value.reason == "CycleDetected"
    assert "ops -> eng -> ops" in str(raised.value)


async def test_validate_group_rejects_multi_node_cycle() -> None:
    """A longer loop through the parent chain is denied."""
    chain = [make_group("b", parent="c"), make_group("c", parent="a")]
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(FakeAdmissionRequest(resource=make_group("a", parent="b"), objects=chain))
    assert raised.value.reason == "CycleDetected"
    assert "a -> b -> c -> a" in str(raised.value)


async def test_validate_group_rejects_entry_into_existing_cycle() -> None:
    """Attaching to a cyclic ancestor chain is denied."""
    cycle = [make_group("a", parent="b"), make_group("b", parent="a")]
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(FakeAdmissionRequest(resource=make_group("leaf", parent="a"), objects=cycle))
    assert raised.value.reason == "CycleDetected"
    assert "leaf -> a -> b -> a" in str(raised.value)


async def test_validate_group_rejects_missing_parent() -> None:
    """A parentRef that does not exist is denied at admission."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(FakeAdmissionRequest(resource=make_group("ops", parent="missing")))
    assert raised.value.reason == "MissingReference"
    assert "missing" in str(raised.value)


async def test_validate_group_rejects_missing_ancestor() -> None:
    """A missing ancestor farther up the chain is denied."""
    request = FakeAdmissionRequest(
        resource=make_group("ops", parent="eng"), objects=[make_group("eng", parent="missing")]
    )
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_group(request)
    assert raised.value.reason == "MissingReference"
    assert "missing" in str(raised.value)


async def test_validate_user_callsign_allows_a_free_callsign() -> None:
    """A callsign no other user holds is admitted."""
    request = FakeAdmissionRequest(
        resource=make_user("user-1", callsign="bob"),
        objects=[make_user("user-2", callsign="charlie")],
    )
    await _validate_user_callsign(request)


async def test_validate_user_callsign_allows_keeping_its_own_callsign() -> None:
    """Updating a user does not collide with the callsign it already holds."""
    user = make_user("user-1", callsign="bob")
    await _validate_user_callsign(FakeAdmissionRequest(operation="UPDATE", resource=user, objects=[user]))


async def test_validate_user_callsign_skips_updates_that_keep_the_callsign() -> None:
    """Approve, revoke and role writes do not pay for a scan of every user."""
    user = make_user("user-1", callsign="bob")
    request = FakeAdmissionRequest(operation="UPDATE", resource=user, old_resource=user, objects=[user])
    await _validate_user_callsign(request)
    assert request.client_calls == 0


async def test_validate_user_callsign_ignores_empty_request() -> None:
    """A request carrying no object is ignored."""
    request = FakeAdmissionRequest[User]()
    await _validate_user_callsign(request)
    assert request.client_calls == 0


async def test_validate_user_callsign_rejects_a_taken_callsign() -> None:
    """Two users cannot hold one callsign, whatever they are named."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_user_callsign(
            FakeAdmissionRequest(
                resource=make_user("user-2", callsign="bob"),
                objects=[make_user("user-1", callsign="bob")],
            )
        )
    assert raised.value.reason == "CallsignTaken"
    assert "user-1" in str(raised.value)


async def test_validate_user_callsign_rejects_a_callsign_taken_in_another_case() -> None:
    """Callsigns are compared folded, so case alone cannot make a second user."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_user_callsign(
            FakeAdmissionRequest(
                resource=make_user("user-2", callsign="Bob"),
                objects=[make_user("user-1", callsign="bob")],
            )
        )
    assert raised.value.reason == "CallsignTaken"
    assert "user-1" in str(raised.value)


async def test_validate_user_callsign_skips_updates_that_only_change_case() -> None:
    """Recasing a callsign collides with nobody, so it does not scan every user."""
    user = make_user("user-1", callsign="BOB")
    request = FakeAdmissionRequest(
        operation="UPDATE",
        resource=user,
        old_resource=make_user("user-1", callsign="bob"),
        objects=[user],
    )
    await _validate_user_callsign(request)
    assert request.client_calls == 0


async def test_validate_user_callsign_rejects_a_rename_onto_a_taken_callsign() -> None:
    """A rename is still checked, so the skip cannot let a duplicate through."""
    renamed = make_user("user-2", callsign="bob")
    request = FakeAdmissionRequest(
        operation="UPDATE",
        resource=renamed,
        old_resource=make_user("user-2", callsign="charlie"),
        objects=[make_user("user-1", callsign="bob")],
    )
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_user_callsign(request)
    assert raised.value.reason == "CallsignTaken"


async def test_validate_user_delete_allows_user_without_bindings() -> None:
    """A User with no UserBindings may be deleted."""
    request = FakeAdmissionRequest(
        operation="DELETE", old_resource=make_user("bob"), objects=[make_binding("charlie", user="charlie")]
    )
    await _validate_user_delete(request)
    assert request.client_calls == 1


async def test_validate_user_delete_ignores_empty_delete() -> None:
    """DELETE-style requests with no object or name are ignored."""
    request = FakeAdmissionRequest[User](operation="DELETE")
    await _validate_user_delete(request)
    assert request.client_calls == 0


async def test_validate_user_delete_rejects_user_with_bindings() -> None:
    """A User named by any UserBinding cannot be deleted."""
    bindings = [make_binding("bob", user="bob", namespace="taky"), make_binding("bob", user="bob", namespace="radio")]
    with pytest.raises(AdmissionDenied) as raised:
        await _validate_user_delete(
            FakeAdmissionRequest(operation="DELETE", old_resource=make_user("bob"), objects=bindings)
        )
    assert raised.value.reason == "HasBindings"
    assert "radio/bob, taky/bob" in str(raised.value)
