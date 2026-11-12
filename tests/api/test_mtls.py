"""Client certificate authentication, with the User list replaced by a fake."""

import base64
import json
from urllib.parse import quote

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import ACCEPTED_CREDENTIALS_ANNOTATION, Group, Role, User
from opendefence_core.api import dependencies
from opendefence_core.api.app import app
from opendefence_core.api.lib.uids import compact
from opendefence_core.certificates import certificate_identity
from tests.factories import make_client_certificate, make_group, make_user, uid
from tests.fakes import FakeList


def _header(*certificates: x509.Certificate) -> str:
    """The value Traefik passTLSClientCert sends: URL-escaped, comma-separated base64 DER."""
    return quote(
        ",".join(base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in certificates), safe=""
    )


def _accept(user: User, certificate: x509.Certificate) -> None:
    """Publish the certificate as the user's accepted credential, as the operator does."""
    assert user.metadata is not None
    entry = {
        "fingerprintSha256": certificate.fingerprint(hashes.SHA256()).hex(),
        "serial": format(certificate.serial_number, "x"),
        "notBefore": certificate.not_valid_before_utc.isoformat(),
        "notAfter": certificate.not_valid_after_utc.isoformat(),
    }
    user.metadata.annotations = {ACCEPTED_CREDENTIALS_ANNOTATION: json.dumps({"version": 1, "accepted": [entry]})}


def _certificate(user: User, **kwargs: int) -> x509.Certificate:
    return make_client_certificate(*certificate_identity(user), **kwargs)


@pytest.fixture
def users(monkeypatch: pytest.MonkeyPatch) -> list[User]:
    """Users the API can list."""
    state: list[User] = []

    async def async_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(state)

    monkeypatch.setattr(User, "async_list", classmethod(async_list))
    return state


@pytest.fixture
def groups(monkeypatch: pytest.MonkeyPatch) -> list[Group]:
    """Groups the API can list."""
    state: list[Group] = []

    async def async_list(cls: type[Group], **kwargs: object) -> FakeList[Group]:
        _ = cls, kwargs
        return FakeList(state)

    monkeypatch.setattr(Group, "async_list", classmethod(async_list))
    return state


@pytest.fixture
def roles(monkeypatch: pytest.MonkeyPatch) -> list[Role]:
    """Roles the API can list."""
    state: list[Role] = []

    async def async_list(cls: type[Role], **kwargs: object) -> FakeList[Role]:
        _ = cls, kwargs
        return FakeList(state)

    monkeypatch.setattr(Role, "async_list", classmethod(async_list))
    return state


async def test_mtls_user_returns_the_certificate_user(users: list[User]) -> None:
    """The accepted certificate authenticates its user; only the first certificate of a chain counts."""
    user, other = make_user("user-alpha"), make_user("user-bravo")
    certificate = _certificate(user)
    _accept(user, certificate)
    users.extend([other, user])
    assert await dependencies.mtls_user(_header(certificate)) is user
    assert await dependencies.mtls_user(_header(certificate, _certificate(other))) is user


async def _assert_rejected(header: str | None) -> None:
    with pytest.raises(HTTPException) as raised:
        await dependencies.mtls_user(header)
    assert raised.value.status_code == 401


async def test_mtls_user_rejects(users: list[User]) -> None:
    """Missing or unreadable certificates, unknown users, and certificates not accepted now are 401."""
    user = make_user("user-alpha")
    _accept(user, _certificate(user))
    users.append(user)
    common_name, _ = certificate_identity(user)
    await _assert_rejected(None)
    await _assert_rejected("not%2Ca%2Ccertificate")
    await _assert_rejected(_header(make_client_certificate(common_name, "urn:example:other")))
    await _assert_rejected(_header(make_client_certificate(common_name, "urn:uuid:not-a-uuid")))
    await _assert_rejected(_header(_certificate(make_user("user-ghost"))))
    await _assert_rejected(_header(_certificate(user, serial=0x9999)))
    # Same serial as the accepted certificate, but another key
    await _assert_rejected(_header(_certificate(user)))


def test_me_with_a_client_certificate(users: list[User], groups: list[Group], roles: list[Role]) -> None:
    """GET /users/me answers for the certificate's user; a valid token without a certificate is 401."""
    _ = groups, roles
    user = make_user("user-alpha", callsign="alpha1")
    certificate = _certificate(user)
    _accept(user, certificate)
    users.append(user)
    client = TestClient(app)
    response = client.get("/api/v3/users/me", headers={"X-Forwarded-Tls-Client-Cert": _header(certificate)})
    assert response.status_code == 200
    assert (response.json()["id"], response.json()["callsign"]) == (compact(uid("user-alpha")), "alpha1")
    app.dependency_overrides[dependencies.jwt_user] = lambda: user
    try:
        assert client.get("/api/v3/users/me").status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("held", "joined", "allowed"),
    [(["superadmin"], [], True), ([], ["admins"], True), (["operator"], [], False)],
)
async def test_superadmin_user(groups: list[Group], held: list[str], joined: list[str], allowed: bool) -> None:
    """The superadmin role counts when held directly or through a group; any other caller is 403."""
    groups.append(make_group("admins", roles=["superadmin"]))
    user = make_user("user-alpha", roles=held, groups=joined)
    if allowed:
        assert await dependencies.superadmin_user(user) is user
        return
    with pytest.raises(HTTPException) as raised:
        await dependencies.superadmin_user(user)
    assert raised.value.status_code == 403


def test_admin_routes_need_superadmin(groups: list[Group]) -> None:
    """A certificate without the superadmin role is 403 on admin routes; no certificate is 401."""
    _ = groups
    client = TestClient(app)
    assert client.get("/api/v3/groups").status_code == 401
    app.dependency_overrides[dependencies.mtls_user] = lambda: make_user("user-alpha")
    try:
        assert client.get("/api/v3/groups").status_code == 403
    finally:
        app.dependency_overrides.clear()
