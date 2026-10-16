"""Invite redemption and token authentication, with the Kubernetes API replaced by fakes."""

from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cloudcoil.errors import ResourceConflict, ResourceNotFound
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from lib_opendefence_core.models.v1alpha1 import Invite, User
from opendefence_core.api import dependencies
from opendefence_core.api.lib import invites
from tests.factories import make_invite, make_user
from tests.fakes import FakeList


@pytest.fixture
def cluster(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Invites to list and Users to get or create, recording writes."""
    state: dict[str, Any] = {"invites": [], "users": {}, "created": [], "status_updates": [], "conflict_on": set()}

    async def async_list(cls: type[Invite], **kwargs: object) -> FakeList[Invite]:
        _ = cls, kwargs
        return FakeList(state["invites"])

    async def async_create(self: User, dry_run: bool = False) -> User:
        if dry_run:
            return self
        if self.metadata is not None and not self.metadata.name:
            self.metadata.name = f"user-{len(state['users'])}"  # The API server fills generateName
        state["created"].append(self)
        state["users"][self.name] = self
        return self

    async def user_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(list(state["users"].values()))

    async def async_update_status(self: Invite, dry_run: bool = False) -> Invite:
        _ = dry_run
        if "invite" in state["conflict_on"]:
            raise ResourceConflict("invite changed", status_code=409)
        state["status_updates"].append(self.status.used if self.status else None)
        return self

    async def async_get(cls: type[User], name: str, namespace: str | None = None) -> User:
        _ = cls, namespace
        if name not in state["users"]:
            raise ResourceNotFound(f"users {name} not found", status_code=404)
        return state["users"][name]

    monkeypatch.setattr(Invite, "async_list", classmethod(async_list))
    monkeypatch.setattr(User, "async_create", async_create)
    monkeypatch.setattr(Invite, "async_update_status", async_update_status)
    monkeypatch.setattr(User, "async_get", classmethod(async_get))
    monkeypatch.setattr(User, "async_list", classmethod(user_list))
    return state


async def test_find_invite_matches_code_of_redeemable_invite(cluster: dict[str, Any]) -> None:
    """Only a redeemable invite with exactly the code is found."""
    cluster["invites"] = [make_invite("used-up", code="SAME", use_count=1, used=1, resolved=True)]
    assert await invites.find_invite("SAME") is None
    cluster["invites"].append(make_invite("open", code="SAME", resolved=True))
    found = await invites.find_invite("SAME")
    assert found is not None
    assert found.name == "open"
    assert await invites.find_invite("OTHER") is None


async def test_redeem_creates_user_and_counts_the_use(cluster: dict[str, Any]) -> None:
    """Redeeming creates the User with the invite's refs and records one use."""
    cluster["invites"] = [make_invite(groups=["team"], use_count=2, resolved=True)]
    user = await invites.redeem("CODE1234", "bravo2")
    assert user.spec.callsign == "bravo2"
    assert user.name != "bravo2"  # Named independently of the callsign
    assert [ref.name for ref in user.spec.group_refs] == ["team"]
    assert cluster["created"] == [user]
    assert cluster["status_updates"] == [1]


async def test_redeem_unknown_code(cluster: dict[str, Any]) -> None:
    """A code without a redeemable invite is rejected."""
    _ = cluster
    with pytest.raises(invites.InviteNotRedeemable):
        await invites.redeem("NOPE", "bravo2")


async def test_redeem_taken_callsign_keeps_the_use(cluster: dict[str, Any]) -> None:
    """A taken callsign fails before the invite use is counted."""
    cluster["invites"] = [make_invite(resolved=True)]
    cluster["users"]["user-0"] = make_user("user-0", callsign="bravo2")
    with pytest.raises(invites.CallsignTaken):
        await invites.redeem("CODE1234", "bravo2")
    assert cluster["status_updates"] == []


async def test_redeem_concurrent_invite_change(cluster: dict[str, Any]) -> None:
    """An invite changed since it was read is not redeemed, and no user is created."""
    cluster["invites"] = [make_invite(resolved=True)]
    cluster["conflict_on"].add("invite")
    with pytest.raises(invites.InviteNotRedeemable):
        await invites.redeem("CODE1234", "bravo2")
    assert cluster["created"] == []


def _credentials(token: str = "token") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def claims(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Claims every token decodes to; an empty dict makes tokens invalid."""
    user = make_user()
    assert user.metadata is not None
    decoded: dict[str, Any] = {"sub": user.name, "uid": user.metadata.uid}

    def decode(token: str) -> dict[str, Any]:
        _ = token
        if not decoded:
            raise jwt.InvalidSignatureError("bad signature")
        return decoded

    monkeypatch.setattr(dependencies, "decode", decode)
    return decoded


async def test_jwt_user_returns_the_token_user(cluster: dict[str, Any], claims: dict[str, Any]) -> None:
    """A valid token for an existing, unrevoked user authenticates them."""
    _ = claims
    cluster["users"]["alpha1"] = make_user("alpha1")
    user = await dependencies.jwt_user(_credentials())
    assert user.name == "alpha1"


@pytest.mark.parametrize("case", ["no-token", "invalid", "missing-user", "recreated-user", "revoked"])
async def test_jwt_user_rejects(cluster: dict[str, Any], claims: dict[str, Any], case: str) -> None:
    """Missing or invalid tokens, deleted, recreated, and revoked users are 401."""
    user = make_user("alpha1", revoked_at=datetime.now(UTC) if case == "revoked" else None)
    if case != "missing-user":
        cluster["users"]["alpha1"] = user
    if case == "recreated-user":
        claims["uid"] = "uid-of-an-earlier-alpha1"
    if case == "invalid":
        claims.clear()
    with pytest.raises(HTTPException) as raised:
        await dependencies.jwt_user(None if case == "no-token" else _credentials())
    assert raised.value.status_code == 401
