"""Group endpoints, with Kubernetes access replaced by fakes."""

from collections.abc import Iterator

import pytest
from cloudcoil.errors import APIError, ResourceConflict
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import Group, User
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.uids import compact
from tests.factories import make_group, make_user, uid
from tests.fakes import FakeList

client = TestClient(app)


def object_id(name: str) -> str:
    """REST id of the object the factories build under this name."""
    return compact(uid(name))


@pytest.fixture
def groups(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Group]]:
    """A root group with one child, and two users, one of them a member of the child."""
    store = [make_group("battalion"), make_group("squad", parent="battalion", roles=["medic"])]
    users = [make_user("user-1", callsign="alpha1", groups=["squad"]), make_user("user-2", callsign="bravo2")]

    async def async_list(cls: type[Group], **kwargs: object) -> FakeList[Group]:
        _ = cls, kwargs
        return FakeList(store)

    async def async_create(self: Group, dry_run: bool = False) -> Group:
        _ = dry_run
        if any(found.name == self.name for found in store):
            raise ResourceConflict(f"groups {self.name} already exists", status_code=409)
        if self.metadata is not None:
            self.metadata.uid = uid(self.name or "")  # The API server assigns the uid
        store.append(self)
        return self

    async def async_update(self: Group, dry_run: bool = False) -> Group:
        _ = dry_run
        return self

    async def async_remove(self: Group, **kwargs: object) -> Group:
        _ = kwargs
        store.remove(self)
        return self

    async def user_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(users)

    async def user_update(self: User, dry_run: bool = False) -> User:
        _ = dry_run
        return self

    monkeypatch.setattr(Group, "async_list", classmethod(async_list))
    monkeypatch.setattr(Group, "async_create", async_create)
    monkeypatch.setattr(Group, "async_update", async_update)
    monkeypatch.setattr(Group, "async_remove", async_remove)
    monkeypatch.setattr(User, "async_list", classmethod(user_list))
    monkeypatch.setattr(User, "async_update", user_update)
    app.dependency_overrides[jwt_user] = lambda: users[0]
    yield store
    app.dependency_overrides.clear()


def test_groups_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/groups").status_code == 401


def test_read_groups(groups: list[Group]) -> None:
    """Listing names the parent by id and carries the granted roles."""
    _ = groups
    response = client.get("/api/v3/groups")
    assert response.status_code == 200
    assert [(group["id"], group["name"], group["parentId"], group["roles"]) for group in response.json()] == [
        (object_id("battalion"), "battalion", None, []),
        (object_id("squad"), "squad", object_id("battalion"), ["medic"]),
    ]


def test_create_and_read_group(groups: list[Group]) -> None:
    """A created group is readable by id, under the parent named by id."""
    _ = groups
    created = client.post(
        "/api/v3/groups",
        json={"name": "platoon", "displayName": "Platoon", "parentId": object_id("battalion")},
    )
    assert created.status_code == 201
    assert client.get(f"/api/v3/groups/{object_id('platoon')}").json() == {
        "id": object_id("platoon"),
        "name": "platoon",
        "displayName": "Platoon",
        "parentId": object_id("battalion"),
        "roles": [],
        "managers": [],
    }


def test_create_group_rejects_an_unknown_parent(groups: list[Group]) -> None:
    """A parent id no group holds is 404."""
    _ = groups
    response = client.post(
        "/api/v3/groups",
        json={"name": "platoon", "displayName": "Platoon", "parentId": object_id("nobody")},
    )
    assert response.status_code == 404


def test_create_duplicate_group(groups: list[Group]) -> None:
    """A name another group holds is 409."""
    _ = groups
    assert client.post("/api/v3/groups", json={"name": "squad", "displayName": "Squad"}).status_code == 409


def test_create_group_rejects_bad_name(groups: list[Group]) -> None:
    """Group names must be Kubernetes resource names."""
    _ = groups
    assert client.post("/api/v3/groups", json={"name": "Not Valid!", "displayName": "X"}).status_code == 422


def test_unknown_group(groups: list[Group]) -> None:
    """An id no group holds is 404, and a bare name is 422."""
    _ = groups
    assert client.get(f"/api/v3/groups/{object_id('missing')}").status_code == 404
    assert client.get("/api/v3/groups/squad").status_code == 422


def test_patch_group_display_name(groups: list[Group]) -> None:
    """Only the sent fields change."""
    _ = groups
    response = client.patch(f"/api/v3/groups/{object_id('squad')}", json={"displayName": "Squad One"})
    assert response.status_code == 200
    assert response.json()["displayName"] == "Squad One"
    assert response.json()["parentId"] == object_id("battalion")


def test_patch_group_clears_the_parent(groups: list[Group]) -> None:
    """Sending a null parent makes the group a root."""
    _ = groups
    response = client.patch(f"/api/v3/groups/{object_id('squad')}", json={"parentId": None})
    assert response.status_code == 200
    assert response.json()["parentId"] is None


def test_patch_group_keeps_the_parent_when_unsent(groups: list[Group]) -> None:
    """Leaving the parent out does not clear it."""
    _ = groups
    patched = client.patch(f"/api/v3/groups/{object_id('squad')}", json={})
    assert patched.json()["parentId"] == object_id("battalion")


def test_delete_group(groups: list[Group]) -> None:
    """A group with no children is deleted."""
    _ = groups
    assert client.delete(f"/api/v3/groups/{object_id('squad')}").status_code == 204
    assert [group.name for group in groups] == ["battalion"]


def test_read_group_members(groups: list[Group]) -> None:
    """Members are the users that name the group directly, summarised by callsign."""
    _ = groups
    response = client.get(f"/api/v3/groups/{object_id('squad')}/members")
    assert [(user["id"], user["callsign"]) for user in response.json()] == [(object_id("user-1"), "alpha1")]


def test_add_and_remove_member(groups: list[Group]) -> None:
    """Membership is stored on the user and both writes are idempotent."""
    _ = groups
    battalion, bravo = object_id("battalion"), object_id("user-2")
    added = client.put(f"/api/v3/groups/{battalion}/members/{bravo}")
    assert added.status_code == 200
    assert client.put(f"/api/v3/groups/{battalion}/members/{bravo}").status_code == 200
    assert client.get(f"/api/v3/groups/{battalion}/members").json()[0]["id"] == bravo
    assert client.delete(f"/api/v3/groups/{battalion}/members/{bravo}").status_code == 204
    assert client.delete(f"/api/v3/groups/{battalion}/members/{bravo}").status_code == 204
    assert client.get(f"/api/v3/groups/{battalion}/members").json() == []


def test_admission_denial_is_a_conflict(groups: list[Group], monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator rejecting a parent cycle is a conflict, not a 500."""
    _ = groups

    async def denied(self: Group, dry_run: bool = False) -> Group:
        _ = self, dry_run
        raise APIError({"message": "Group cycle"}, status_code=403)

    monkeypatch.setattr(Group, "async_update", denied)
    squad = object_id("squad")
    response = client.patch(f"/api/v3/groups/{squad}", json={"parentId": squad})
    assert response.status_code == 409
    assert "cycle" in response.json()["detail"]


def test_member_endpoints_need_both_objects(groups: list[Group]) -> None:
    """An unknown group or user is 404."""
    _ = groups
    assert client.put(f"/api/v3/groups/{object_id('missing')}/members/{object_id('user-2')}").status_code == 404
    assert client.put(f"/api/v3/groups/{object_id('squad')}/members/{object_id('user-99')}").status_code == 404
