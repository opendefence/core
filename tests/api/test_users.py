"""User endpoints, with Kubernetes access replaced by fakes."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from cloudcoil.errors import ResourceNotFound
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from tests.factories import make_user
from tests.fakes import FakeList

client = TestClient(app)


@pytest.fixture
def users(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[User]]:
    """One user in each state, authenticated as the active one."""
    now = datetime.now(UTC)
    active = make_user("alpha1", roles=["superadmin"], approved_at=now)
    store = [
        make_user("bravo2", approval_code="ABCD1234"),
        active,
        make_user("charl3", approved_at=now, revoked_at=now),
    ]

    async def async_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(store)

    async def async_get(cls: type[User], name: str, namespace: str | None = None) -> User:
        _ = cls, namespace
        user = next((found for found in store if found.name == name), None)
        if user is None:
            raise ResourceNotFound(f"users {name} not found", status_code=404)
        return user

    async def async_update(self: User, dry_run: bool = False) -> User:
        _ = dry_run
        return self

    monkeypatch.setattr(User, "async_list", classmethod(async_list))
    monkeypatch.setattr(User, "async_get", classmethod(async_get))
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
        "name": "alpha1",
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
    assert [(user["name"], user["state"], user["approvalCode"]) for user in response.json()] == [
        ("bravo2", "pending", "ABCD1234"),
        ("alpha1", "active", None),
        ("charl3", "revoked", None),
    ]


def test_read_users_by_state(users: list[User]) -> None:
    """The state filter narrows the listing."""
    _ = users
    response = client.get("/api/v3/users", params={"state": "pending"})
    assert [user["name"] for user in response.json()] == ["bravo2"]


def test_read_user(users: list[User]) -> None:
    """A user is read by callsign."""
    _ = users
    assert client.get("/api/v3/users/bravo2").json()["callsign"] == "bravo2"


def test_unknown_user(users: list[User]) -> None:
    """A callsign no user holds is 404."""
    _ = users
    assert client.get("/api/v3/users/zulu99").status_code == 404


def test_approve_and_revoke(users: list[User]) -> None:
    """Approving and revoking move the user between states."""
    _ = users
    assert client.post("/api/v3/users/bravo2/approve").json()["state"] == "active"
    assert client.post("/api/v3/users/bravo2/revoke").json()["state"] == "revoked"


def test_cannot_revoke_yourself(users: list[User]) -> None:
    """An administrator cannot revoke their own access."""
    _ = users
    assert client.post("/api/v3/users/alpha1/revoke").status_code == 409
