"""Role endpoints, with Kubernetes access replaced by fakes."""

from collections.abc import Iterator

import pytest
from cloudcoil.errors import ResourceConflict, ResourceNotFound
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import Group, Role, User
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from tests.factories import make_group, make_role, make_user
from tests.fakes import FakeList

client = TestClient(app)


@pytest.fixture
def roles(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Role]]:
    """One managed role and one integration-owned role."""
    store = [make_role("operator"), make_role("tak-admin", owner="tak")]

    async def async_list(cls: type[Role], **kwargs: object) -> FakeList[Role]:
        _ = cls, kwargs
        return FakeList(store)

    async def async_get(cls: type[Role], name: str, namespace: str | None = None) -> Role:
        _ = cls, namespace
        role = next((found for found in store if found.name == name), None)
        if role is None:
            raise ResourceNotFound(f"roles {name} not found", status_code=404)
        return role

    async def async_create(self: Role, dry_run: bool = False) -> Role:
        _ = dry_run
        if any(found.name == self.name for found in store):
            raise ResourceConflict(f"roles {self.name} already exists", status_code=409)
        store.append(self)
        return self

    async def async_remove(self: Role, **kwargs: object) -> Role:
        _ = kwargs
        store.remove(self)
        return self

    monkeypatch.setattr(Role, "async_list", classmethod(async_list))
    monkeypatch.setattr(Role, "async_get", classmethod(async_get))
    monkeypatch.setattr(Role, "async_create", async_create)
    monkeypatch.setattr(Role, "async_remove", async_remove)
    app.dependency_overrides[jwt_user] = lambda: make_user("alpha1")
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def no_referrers(monkeypatch: pytest.MonkeyPatch) -> None:
    """No user or group names any role."""
    _seed(monkeypatch, users=[make_user("alpha1")], groups=[make_group("team")])


def _seed(monkeypatch: pytest.MonkeyPatch, *, users: list[User], groups: list[Group]) -> None:
    async def list_users(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(users)

    async def list_groups(cls: type[Group], **kwargs: object) -> FakeList[Group]:
        _ = cls, kwargs
        return FakeList(groups)

    monkeypatch.setattr(User, "async_list", classmethod(list_users))
    monkeypatch.setattr(Group, "async_list", classmethod(list_groups))


def test_roles_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/roles").status_code == 401


def test_read_roles(roles: list[Role]) -> None:
    """Listing marks which roles an integration owns."""
    _ = roles
    response = client.get("/api/v3/roles")
    assert response.status_code == 200
    assert [(role["name"], role["managed"]) for role in response.json()] == [
        ("operator", False),
        ("tak-admin", True),
    ]


def test_create_and_read_role(roles: list[Role]) -> None:
    """A created role is readable under its name."""
    _ = roles
    response = client.post("/api/v3/roles", json={"name": "medic", "displayName": "Medic"})
    assert response.status_code == 201
    assert response.json() == {
        "name": "medic",
        "displayName": "Medic",
        "managed": False,
        "createdAt": None,
    }
    assert client.get("/api/v3/roles/medic").json()["displayName"] == "Medic"


def test_create_rejects_a_bad_name(roles: list[Role]) -> None:
    """The name has to be a resource name."""
    _ = roles
    assert client.post("/api/v3/roles", json={"name": "Medic Role", "displayName": "Medic"}).status_code == 422


def test_create_duplicate_role(roles: list[Role]) -> None:
    """A name another role holds is a conflict."""
    _ = roles
    assert client.post("/api/v3/roles", json={"name": "operator", "displayName": "Other"}).status_code == 409


def test_unknown_role(roles: list[Role]) -> None:
    """A name no role holds is 404."""
    _ = roles
    assert client.get("/api/v3/roles/nobody").status_code == 404
    assert client.delete("/api/v3/roles/nobody").status_code == 404
    assert client.get("/api/v3/roles/nobody/members").status_code == 404


def test_delete_role(roles: list[Role], no_referrers: None) -> None:
    """Deleting a role nothing names removes it."""
    _ = no_referrers
    assert client.delete("/api/v3/roles/operator").status_code == 204
    assert [role.name for role in roles] == ["tak-admin"]


def test_managed_role_cannot_be_deleted(roles: list[Role]) -> None:
    """An integration owns its role, so the API refuses to delete it."""
    _ = roles
    assert client.delete("/api/v3/roles/tak-admin").status_code == 409


def test_delete_refuses_a_named_role(roles: list[Role], monkeypatch: pytest.MonkeyPatch) -> None:
    """A role someone still names cannot be deleted."""
    _ = roles
    _seed(monkeypatch, users=[make_user("alpha1", roles=["operator"])], groups=[make_group("team", roles=["operator"])])

    response = client.delete("/api/v3/roles/operator")

    assert response.status_code == 409
    assert response.json()["detail"] == "Role is still named by: Group/team, User/alpha1"


def test_role_members(roles: list[Role], monkeypatch: pytest.MonkeyPatch) -> None:
    """Members are the users naming the role directly."""
    _ = roles
    _seed(monkeypatch, users=[make_user("alpha1", roles=["operator"]), make_user("bravo2")], groups=[])

    response = client.get("/api/v3/roles/operator/members")

    assert response.status_code == 200
    assert [user["name"] for user in response.json()] == ["alpha1"]
