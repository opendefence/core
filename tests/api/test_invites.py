"""Invite management endpoints, with the Kubernetes API replaced by fakes."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from cloudcoil.resources import Resource
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import Group, Invite, InviteSpec, Role
from opendefence_core.api import lookups
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.uids import compact, ids_by_name
from opendefence_core.api.routes.invites import views
from tests.factories import make_group, make_invite, make_role, make_user, uid
from tests.fakes import FakeList

client = TestClient(app)

ABC12 = compact(uid("invite-abc12"))


async def _none_by_name(kind: type[Role] | type[Group]) -> dict[str, str]:
    """No roles or groups exist unless a test says so."""
    _ = kind
    return {}


@pytest.fixture
def invites(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Invite]]:
    """One invite to read and write, keyed by id."""
    store = {ABC12: make_invite("invite-abc12", use_count=3)}

    async def list_invites() -> list[Invite]:
        return list(store.values())

    async def invite_or_404(invite_id: str) -> Invite:
        found = store.get(compact(invite_id))
        if found is None:
            raise HTTPException(404)
        return found

    async def unique_invite_code() -> str:
        return "NEWCODE1"

    async def create_invite(spec: InviteSpec) -> Invite:
        created = make_invite("invite-new", code=spec.code, use_count=spec.use_count)
        created.spec.role_refs = spec.role_refs
        created.spec.group_refs = spec.group_refs
        store[compact(uid("invite-new"))] = created
        return created

    async def update_invite(invite: Invite, spec: InviteSpec) -> Invite:
        invite.spec = spec
        return invite

    async def delete_invite(invite: Invite) -> None:
        del store[compact(uid(invite.name or ""))]

    monkeypatch.setattr(views, "list_invites", list_invites)
    monkeypatch.setattr(views, "invite_or_404", invite_or_404)
    monkeypatch.setattr(views, "unique_invite_code", unique_invite_code)
    monkeypatch.setattr(views, "create_invite", create_invite)
    monkeypatch.setattr(views, "update_invite", update_invite)
    monkeypatch.setattr(views, "delete_invite", delete_invite)
    monkeypatch.setattr(views, "ids_by_name", _none_by_name)
    app.dependency_overrides[jwt_user] = lambda: make_user("alpha1")
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def granted(invites: dict[str, Invite], monkeypatch: pytest.MonkeyPatch) -> None:
    """A role and a group an invite can grant. Replaces the empty default above."""
    _ = invites
    roles = {"medic": make_role("medic")}
    groups = {"squad": make_group("squad")}

    async def role_or_404(role_id: str) -> Role:
        found = next((role for role in roles.values() if role.metadata and role.metadata.uid == role_id), None)
        if found is None:
            raise HTTPException(404)
        return found

    async def group_or_404(group_id: str) -> Group:
        found = next((group for group in groups.values() if group.metadata and group.metadata.uid == group_id), None)
        if found is None:
            raise HTTPException(404)
        return found

    async def ids_by_name(kind: type[Role] | type[Group]) -> dict[str, str]:
        found = roles if kind is Role else groups
        return {name: compact(uid(name)) for name in found}

    monkeypatch.setattr(views, "role_or_404", role_or_404)
    monkeypatch.setattr(views, "group_or_404", group_or_404)
    monkeypatch.setattr(views, "ids_by_name", ids_by_name)


def test_invites_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/invites").status_code == 401


def test_read_invites(invites: dict[str, Invite]) -> None:
    """Listing shows the id, the code, the limits, and how often the invite was used."""
    _ = invites
    response = client.get("/api/v3/invites")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": ABC12,
            "code": "CODE1234",
            "roleIds": [],
            "groupIds": [],
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
    assert invites[compact(uid("invite-new"))].spec.use_count == 5


def test_add_invite_grants_roles_and_groups(invites: dict[str, Invite], granted: None) -> None:
    """Granted roles and groups are sent as ids and stored as name refs."""
    _ = granted
    response = client.post(
        "/api/v3/invites",
        json={"roleIds": [compact(uid("medic"))], "groupIds": [compact(uid("squad"))]},
    )
    assert response.status_code == 201
    created = invites[compact(uid("invite-new"))]
    assert [ref.name for ref in created.spec.role_refs] == ["medic"]
    assert [ref.name for ref in created.spec.group_refs] == ["squad"]
    assert response.json()["roleIds"] == [compact(uid("medic"))]
    assert response.json()["groupIds"] == [compact(uid("squad"))]


def test_add_invite_rejects_unknown_grants(invites: dict[str, Invite], granted: None) -> None:
    """An id no role holds is 404."""
    _ = invites, granted
    response = client.post("/api/v3/invites", json={"roleIds": [compact(uid("nobody"))]})
    assert response.status_code == 404


def test_add_invite_rejects_a_malformed_id(invites: dict[str, Invite]) -> None:
    """A grant that is not an id at all is rejected before any lookup."""
    _ = invites
    assert client.post("/api/v3/invites", json={"roleIds": ["medic"]}).status_code == 422


def test_patch_invite_changes_only_sent_fields(invites: dict[str, Invite]) -> None:
    """A patch of useCount leaves validUntil alone."""
    invites[ABC12].spec.valid_until = datetime(2137, 1, 1, tzinfo=UTC)
    response = client.patch(f"/api/v3/invites/{ABC12}", json={"useCount": 9})
    assert response.status_code == 200
    assert response.json()["useCount"] == 9
    assert response.json()["validUntil"] == "2137-01-01T00:00:00Z"


def test_remove_invite(invites: dict[str, Invite]) -> None:
    """Deleting removes the invite."""
    assert client.delete(f"/api/v3/invites/{ABC12}").status_code == 204
    assert ABC12 not in invites


def test_unknown_invite(invites: dict[str, Invite]) -> None:
    """An id no managed invite holds is 404."""
    _ = invites
    assert client.get(f"/api/v3/invites/{compact(uid('invite-missing'))}").status_code == 404


def test_invite_id_must_be_an_id(invites: dict[str, Invite]) -> None:
    """A resource name is no longer accepted in the path."""
    _ = invites
    assert client.get("/api/v3/invites/invite-abc12").status_code == 422


@pytest.mark.parametrize(
    ("name", "auto_approve", "found"),
    [("invite-abc12", False, True), ("invite-abc12", True, False), ("invite-missing", False, False)],
)
async def test_invite_or_404_hides_auto_approving_invites(
    monkeypatch: pytest.MonkeyPatch, name: str, auto_approve: bool, found: bool
) -> None:
    """Auto-approving invites stay hidden."""
    stored = [make_invite("invite-abc12", auto_approve=auto_approve)]

    async def async_list(cls: type[Invite], **kwargs: object) -> FakeList[Invite]:
        _ = cls, kwargs
        return FakeList(stored)

    monkeypatch.setattr(Invite, "async_list", classmethod(async_list))

    if found:
        assert (await lookups.invite_or_404(uid(name))).name == name
    else:
        with pytest.raises(HTTPException):
            await lookups.invite_or_404(uid(name))


@pytest.mark.parametrize("kind", [Role, Group])
async def test_grant_lookups_resolve_by_id(monkeypatch: pytest.MonkeyPatch, kind: type[Role] | type[Group]) -> None:
    """A granted role or group is found by id, and an unknown id is 404."""
    stored: list[Resource] = [make_role("medic") if kind is Role else make_group("squad")]
    name = stored[0].name or ""

    async def async_list(cls: type[Resource], **kwargs: object) -> FakeList[Resource]:
        _ = cls, kwargs
        return FakeList(stored)

    monkeypatch.setattr(kind, "async_list", classmethod(async_list))
    resolve = lookups.role_or_404 if kind is Role else lookups.group_or_404

    assert (await resolve(uid(name))).name == name
    assert await ids_by_name(kind) == {name: compact(uid(name))}
    with pytest.raises(HTTPException):
        await resolve(uid("nobody"))
