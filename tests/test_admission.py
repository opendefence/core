"""Group parent-chain admission validation."""

from typing import cast

import pytest
from cloudcoil.admission import AdmissionDenied, AdmissionRequest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.errors import ResourceNotFound

from opendefence_core.k8s_operator.controllers.groups import validate_group
from opendefence_core.k8s_operator.controllers.users import validate_user_delete
from opendefence_core.k8s_operator.models.v1alpha1 import (
    API_VERSION,
    Group,
    GroupSpec,
    ObjectRef,
    User,
    UserBinding,
    UserBindingSpec,
    UserSpec,
)


def _group(name: str, *, parent: str | None = None) -> Group:
    return Group(
        api_version=API_VERSION,
        kind="Group",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=GroupSpec(
            name=name,
            display_name=name,
            parent_ref=ObjectRef(name=parent) if parent else None,
        ),
    )


class FakeGroupList:
    """Async-iterable stand-in for a live Group list page."""

    def __init__(self, groups: list[Group]) -> None:
        self.items = groups

    async def __aiter__(self):
        for group in self.items:
            yield group


class FakeGroupClient:
    """Live-read stand-in that raises ResourceNotFound for unknown names."""

    def __init__(self, groups: dict[str, Group]) -> None:
        self._groups = groups

    async def get(self, name: str, namespace: str | None = None) -> Group:
        _ = namespace
        group = self._groups.get(name)
        if group is None:
            raise ResourceNotFound({"message": f"Group {name} not found"}, status_code=404)
        return group

    async def list(self, **kwargs: object) -> FakeGroupList:
        _ = kwargs
        return FakeGroupList(list(self._groups.values()))


class FakeAdmissionRequest:
    """Minimal AdmissionRequest stand-in for live parent lookups."""

    def __init__(
        self,
        resource: Group | None,
        groups: dict[str, Group] | None = None,
        *,
        operation: str = "CREATE",
        old_resource: Group | None = None,
        name: str = "",
    ) -> None:
        self.resource = resource
        self.old_resource = old_resource
        self.operation = operation
        self.name = (
            name
            or (old_resource.name if old_resource is not None else "")
            or (resource.name if resource is not None else "")
        )
        self._client = FakeGroupClient(groups or {})
        self.client_calls = 0

    async def client(self, resource: type[Group]) -> FakeGroupClient:
        _ = resource
        self.client_calls += 1
        return self._client


async def _validate(
    resource: Group | None,
    groups: dict[str, Group] | None = None,
    *,
    operation: str = "CREATE",
    old_resource: Group | None = None,
    name: str = "",
) -> FakeAdmissionRequest:
    request = FakeAdmissionRequest(
        resource,
        groups,
        operation=operation,
        old_resource=old_resource,
        name=name,
    )
    await validate_group(cast(AdmissionRequest[Group], request))
    return request


@pytest.mark.asyncio
async def test_validate_group_allows_acyclic_parent() -> None:
    """A child may name an existing ancestor chain."""
    root = _group("root")
    engineering = _group("engineering", parent="root")
    await _validate(_group("ops", parent="engineering"), {"root": root, "engineering": engineering})


@pytest.mark.asyncio
async def test_validate_group_allows_missing_resource_snapshot() -> None:
    """DELETE-style requests with no object or name are ignored."""
    request = await _validate(None, operation="DELETE")
    assert request.client_calls == 0


@pytest.mark.asyncio
async def test_validate_group_allows_delete_without_children() -> None:
    """A leaf group may be deleted while its parent remains."""
    parent = _group("ops")
    leaf = _group("eng", parent="ops")
    await _validate(
        None,
        {"ops": parent, "eng": leaf},
        operation="DELETE",
        old_resource=leaf,
    )


@pytest.mark.asyncio
async def test_validate_group_rejects_delete_with_children() -> None:
    """A group named as parentRef by another group cannot be deleted."""
    parent = _group("ops")
    child = _group("eng", parent="ops")
    other = _group("platform", parent="ops")
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(
            None,
            {"ops": parent, "eng": child, "platform": other},
            operation="DELETE",
            old_resource=parent,
        )
    assert raised.value.reason == "HasChildren"
    assert "eng, platform" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_allows_root_group_without_client() -> None:
    """Groups with no parentRef do not perform live reads."""
    request = await _validate(_group("ops"))
    assert request.client_calls == 0


@pytest.mark.asyncio
async def test_validate_group_rejects_self_parent() -> None:
    """Direct self-parent is denied."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("ops", parent="ops"))
    assert raised.value.reason == "SelfReference"
    assert "same object" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_rejects_two_node_cycle() -> None:
    """ops -> eng -> ops is denied."""
    eng = _group("eng", parent="ops")
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("ops", parent="eng"), {"eng": eng})
    assert raised.value.reason == "CycleDetected"
    assert "ops -> eng -> ops" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_rejects_multi_node_cycle() -> None:
    """A longer loop through the parent chain is denied."""
    b = _group("b", parent="c")
    c = _group("c", parent="a")
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("a", parent="b"), {"b": b, "c": c})
    assert raised.value.reason == "CycleDetected"
    assert "a -> b -> c -> a" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_rejects_entry_into_existing_cycle() -> None:
    """Attaching to a cyclic ancestor chain is denied."""
    a = _group("a", parent="b")
    b = _group("b", parent="a")
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("leaf", parent="a"), {"a": a, "b": b})
    assert raised.value.reason == "CycleDetected"
    assert "leaf -> a -> b -> a" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_rejects_missing_parent() -> None:
    """A parentRef that does not exist is denied at admission."""
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("ops", parent="missing"))
    assert raised.value.reason == "MissingReference"
    assert "missing" in str(raised.value)


@pytest.mark.asyncio
async def test_validate_group_rejects_missing_ancestor() -> None:
    """A missing ancestor farther up the chain is denied."""
    eng = _group("eng", parent="missing")
    with pytest.raises(AdmissionDenied) as raised:
        await _validate(_group("ops", parent="eng"), {"eng": eng})
    assert raised.value.reason == "MissingReference"
    assert "missing" in str(raised.value)


def _user(name: str) -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=UserSpec(callsign=name),
    )


def _binding(name: str, *, user: str, namespace: str = "taky") -> UserBinding:
    return UserBinding(
        api_version=API_VERSION,
        kind="UserBinding",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=f"uid-{namespace}-{name}"),
        spec=UserBindingSpec(user_ref=ObjectRef(name=user)),
    )


class FakeBindingList:
    """Async-iterable stand-in for a live UserBinding list page."""

    def __init__(self, bindings: list[UserBinding]) -> None:
        self.items = bindings

    async def __aiter__(self):
        for binding in self.items:
            yield binding


class FakeBindingClient:
    """Live-read stand-in for cluster-wide UserBinding lists."""

    def __init__(self, bindings: list[UserBinding]) -> None:
        self._bindings = bindings

    async def list(self, **kwargs: object) -> FakeBindingList:
        _ = kwargs
        return FakeBindingList(self._bindings)


class FakeUserDeleteRequest:
    """Minimal AdmissionRequest stand-in for User DELETE checks."""

    def __init__(
        self,
        *,
        old_resource: User | None,
        bindings: list[UserBinding] | None = None,
        name: str = "",
    ) -> None:
        self.resource: User | None = None
        self.old_resource = old_resource
        self.operation = "DELETE"
        self.name = name or (old_resource.name if old_resource is not None else "")
        self._client = FakeBindingClient(bindings or [])
        self.client_calls = 0

    async def client(self, resource: type[UserBinding]) -> FakeBindingClient:
        _ = resource
        self.client_calls += 1
        return self._client


@pytest.mark.asyncio
async def test_validate_user_delete_allows_user_without_bindings() -> None:
    """A User with no UserBindings may be deleted."""
    request = FakeUserDeleteRequest(old_resource=_user("bob"), bindings=[_binding("charlie", user="charlie")])
    await validate_user_delete(cast(AdmissionRequest[User], request))
    assert request.client_calls == 1


@pytest.mark.asyncio
async def test_validate_user_delete_ignores_empty_delete() -> None:
    """DELETE-style requests with no object or name are ignored."""
    request = FakeUserDeleteRequest(old_resource=None)
    await validate_user_delete(cast(AdmissionRequest[User], request))
    assert request.client_calls == 0


@pytest.mark.asyncio
async def test_validate_user_delete_rejects_user_with_bindings() -> None:
    """A User named by any UserBinding cannot be deleted."""
    request = FakeUserDeleteRequest(
        old_resource=_user("bob"),
        bindings=[
            _binding("bob", user="bob", namespace="taky"),
            _binding("bob", user="bob", namespace="radio"),
        ],
    )
    with pytest.raises(AdmissionDenied) as raised:
        await validate_user_delete(cast(AdmissionRequest[User], request))
    assert raised.value.reason == "HasBindings"
    assert "radio/bob, taky/bob" in str(raised.value)
