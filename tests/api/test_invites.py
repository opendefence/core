"""Invite management endpoints, with the Kubernetes API replaced by fakes."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from cloudcoil.errors import ResourceNotFound
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import Invite, InviteSpec
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib import invites as lib_invites
from opendefence_core.api.routes.invites import views
from tests.factories import make_invite, make_user

client = TestClient(app)


@pytest.fixture
def invites(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Invite]]:
    """One invite to read and write, keyed by name."""
    store = {"invite-abc12": make_invite("invite-abc12", use_count=3)}

    async def list_invites() -> list[Invite]:
        return list(store.values())

    async def get_invite(name: str) -> Invite | None:
        return store.get(name)

    async def unique_invite_code() -> str:
        return "NEWCODE1"

    async def create_invite(spec: InviteSpec) -> Invite:
        store["invite-new"] = make_invite("invite-new", code=spec.code, use_count=spec.use_count)
        return store["invite-new"]

    async def update_invite(invite: Invite, spec: InviteSpec) -> Invite:
        invite.spec = spec
        return invite

    async def delete_invite(invite: Invite) -> None:
        del store[invite.name or ""]

    monkeypatch.setattr(views, "list_invites", list_invites)
    monkeypatch.setattr(views, "get_invite", get_invite)
    monkeypatch.setattr(views, "unique_invite_code", unique_invite_code)
    monkeypatch.setattr(views, "create_invite", create_invite)
    monkeypatch.setattr(views, "update_invite", update_invite)
    monkeypatch.setattr(views, "delete_invite", delete_invite)
    app.dependency_overrides[jwt_user] = lambda: make_user("alpha1")
    yield store
    app.dependency_overrides.clear()


def test_invites_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/invites").status_code == 401


def test_read_invites(invites: dict[str, Invite]) -> None:
    """Listing shows the code, the limits, and how often the invite was used."""
    _ = invites
    response = client.get("/api/v3/invites")
    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "invite-abc12",
            "code": "CODE1234",
            "roleRefs": [],
            "groupRefs": [],
            "useCount": 3,
            "used": 0,
            "validUntil": None,
            "createdAt": None,
        }
    ]


def test_add_invite(invites: dict[str, Invite]) -> None:
    """Creating generates the code rather than taking one from the caller."""
    response = client.post("/api/v3/invites", json={"useCount": 5, "code": "CHOSEN"})
    assert response.status_code == 201
    assert response.json()["code"] == "NEWCODE1"
    assert invites["invite-new"].spec.use_count == 5


def test_patch_invite_changes_only_sent_fields(invites: dict[str, Invite]) -> None:
    """A patch of useCount leaves validUntil alone."""
    invites["invite-abc12"].spec.valid_until = datetime(2137, 1, 1, tzinfo=UTC)
    response = client.patch("/api/v3/invites/invite-abc12", json={"useCount": 9})
    assert response.status_code == 200
    assert response.json()["useCount"] == 9
    assert response.json()["validUntil"] == "2137-01-01T00:00:00Z"


def test_remove_invite(invites: dict[str, Invite]) -> None:
    """Deleting removes the invite."""
    assert client.delete("/api/v3/invites/invite-abc12").status_code == 204
    assert "invite-abc12" not in invites


def test_unknown_invite(invites: dict[str, Invite]) -> None:
    """A name no managed invite holds is 404."""
    _ = invites
    assert client.get("/api/v3/invites/invite-missing").status_code == 404


@pytest.mark.parametrize(
    ("name", "auto_approve", "found"),
    [("invite-abc12", False, True), ("invite-abc12", True, False), ("invite-missing", False, False)],
)
async def test_get_invite_hides_auto_approving_invites(
    monkeypatch: pytest.MonkeyPatch, name: str, auto_approve: bool, found: bool
) -> None:
    """Auto-approving invites stay hidden."""
    stored = make_invite("invite-abc12", auto_approve=auto_approve)

    async def async_get(cls: type[Invite], invite: str, namespace: str | None = None) -> Invite:
        _ = cls, namespace
        if invite != stored.name:
            raise ResourceNotFound(f"invites {invite} not found", status_code=404)
        return stored

    monkeypatch.setattr(Invite, "async_get", classmethod(async_get))

    assert (await lib_invites.get_invite(name) is not None) is found
