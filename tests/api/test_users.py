"""User endpoints, with Kubernetes access replaced by fakes."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.uids import compact
from tests.factories import make_user, uid
from tests.fakes import FakeList

client = TestClient(app)


def user_id(name: str) -> str:
    """REST id of the user the factories build under this name."""
    return compact(uid(name))


@pytest.fixture
def users(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[User]]:
    """One user in each state, authenticated as the active one. Names differ from callsigns."""
    now = datetime.now(UTC)
    active = make_user("user-1", callsign="alpha1", roles=["superadmin"], approved_at=now)
    store = [
        make_user("user-2", callsign="bravo2", approval_code="ABCD1234"),
        active,
        make_user("user-3", callsign="charl3", approved_at=now, revoked_at=now),
    ]

    async def async_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(store)

    async def async_update(self: User, dry_run: bool = False) -> User:
        _ = dry_run
        return self

    monkeypatch.setattr(User, "async_list", classmethod(async_list))
    monkeypatch.setattr(User, "async_update", async_update)
    app.dependency_overrides[jwt_user] = lambda: active
    yield store
    app.dependency_overrides.clear()


def test_users_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/users").status_code == 401


def test_me(users: list[User]) -> None:
    """The caller sees their own identity, state, and role names."""
    _ = users
    response = client.get("/api/v3/users/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": user_id("user-1"),
        "callsign": "alpha1",
        "state": "active",
        "roles": ["superadmin"],
        "approvalCode": None,
    }


def test_read_users(users: list[User]) -> None:
    """Listing carries the state and the approval code."""
    _ = users
    response = client.get("/api/v3/users")
    assert response.status_code == 200
    assert [(user["id"], user["state"], user["approvalCode"]) for user in response.json()] == [
        (user_id("user-2"), "pending", "ABCD1234"),
        (user_id("user-1"), "active", None),
        (user_id("user-3"), "revoked", None),
    ]


def test_read_users_by_state(users: list[User]) -> None:
    """The state filter narrows the listing."""
    _ = users
    response = client.get("/api/v3/users", params={"state": "pending"})
    assert [user["id"] for user in response.json()] == [user_id("user-2")]


def test_read_user(users: list[User]) -> None:
    """A user is read by id, in either accepted form."""
    _ = users
    assert client.get(f"/api/v3/users/{user_id('user-2')}").json()["callsign"] == "bravo2"
    assert client.get(f"/api/v3/users/{uid('user-2')}").json()["callsign"] == "bravo2"


def test_read_user_rejects_names_and_callsigns(users: list[User]) -> None:
    """Neither the resource name nor the callsign addresses a user any more."""
    _ = users
    assert client.get("/api/v3/users/user-2").status_code == 422
    assert client.get("/api/v3/users/bravo2").status_code == 422


def test_unknown_user(users: list[User]) -> None:
    """An id no user holds is 404."""
    _ = users
    assert client.get(f"/api/v3/users/{user_id('user-99')}").status_code == 404


def test_rename_user(users: list[User]) -> None:
    """A rename changes the callsign and keeps the id."""
    _ = users
    response = client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "delta4"})
    assert response.status_code == 200
    assert response.json()["id"] == user_id("user-2")
    assert response.json()["callsign"] == "delta4"


def test_rename_keeps_its_own_callsign(users: list[User]) -> None:
    """Renaming to the callsign the user already holds is not a conflict."""
    _ = users
    assert client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "bravo2"}).status_code == 200


def test_rename_to_a_taken_callsign(users: list[User]) -> None:
    """A callsign another user holds is 409."""
    _ = users
    assert client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "alpha1"}).status_code == 409


def test_rename_to_a_callsign_taken_in_another_case(users: list[User]) -> None:
    """Callsigns are compared folded, so case alone does not free one."""
    _ = users
    assert client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "ALPHA1"}).status_code == 409


def test_rename_can_change_only_the_case(users: list[User]) -> None:
    """A user may recase its own callsign, and it is stored as typed."""
    _ = users
    response = client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "Bravo2"})
    assert response.status_code == 200
    assert response.json()["callsign"] == "Bravo2"


def test_rename_revoked_user(users: list[User]) -> None:
    """A revoked user keeps its callsign."""
    _ = users
    assert client.patch(f"/api/v3/users/{user_id('user-3')}", json={"callsign": "delta4"}).status_code == 409


def test_rename_rejects_bad_callsign(users: list[User]) -> None:
    """Callsigns must match the User callsign pattern."""
    _ = users
    assert client.patch(f"/api/v3/users/{user_id('user-2')}", json={"callsign": "Not Valid!"}).status_code == 422


def test_approve_and_revoke(users: list[User]) -> None:
    """Approving and revoking move the user between states."""
    _ = users
    target = user_id("user-2")
    assert client.post(f"/api/v3/users/{target}/approve").json()["state"] == "active"
    assert client.post(f"/api/v3/users/{target}/revoke").json()["state"] == "revoked"


def test_cannot_revoke_yourself(users: list[User]) -> None:
    """An administrator cannot revoke their own access, named by either form of their id."""
    _ = users
    assert client.post(f"/api/v3/users/{user_id('user-1')}/revoke").status_code == 409
    assert client.post(f"/api/v3/users/{uid('user-1')}/revoke").status_code == 409


def test_approve_unknown_user(users: list[User]) -> None:
    """An id no user holds is 404 before anything is written."""
    _ = users
    assert client.post(f"/api/v3/users/{user_id('user-99')}/approve").status_code == 404
