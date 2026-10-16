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

    monkeypatch.setattr(User, "async_list", classmethod(async_list))
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
