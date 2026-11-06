"""Client certificate authentication, with the User list replaced by a fake."""

import base64
import json
from urllib.parse import quote

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from fastapi import HTTPException

from lib_opendefence_core.models.v1alpha1 import ACCEPTED_CREDENTIALS_ANNOTATION, User
from opendefence_core.api import dependencies
from opendefence_core.certificates import certificate_identity
from tests.factories import make_client_certificate, make_user
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


async def test_mtls_user_returns_the_certificate_user(users: list[User]) -> None:
    """The accepted certificate authenticates its user; only the first certificate of a chain counts."""
    user, other = make_user("user-alpha"), make_user("user-bravo")
    certificate = _certificate(user)
    _accept(user, certificate)
    users.extend([other, user])
    assert await dependencies.mtls_user(_header(certificate)) is user
    assert await dependencies.mtls_user(_header(certificate, _certificate(other))) is user


@pytest.mark.parametrize(
    "case",
    ["no-header", "garbage", "no-uuid-san", "not-a-uuid", "unknown-uid", "not-accepted", "same-serial-other-key"],
)
async def test_mtls_user_rejects(users: list[User], case: str) -> None:
    """Missing or unreadable certificates, unknown users, and certificates not accepted now are 401."""
    user = make_user("user-alpha")
    accepted = _certificate(user)
    _accept(user, accepted)
    users.append(user)
    common_name, _ = certificate_identity(user)
    presented = {
        "no-uuid-san": make_client_certificate(common_name, "urn:example:other"),
        "not-a-uuid": make_client_certificate(common_name, "urn:uuid:not-a-uuid"),
        "unknown-uid": _certificate(make_user("user-ghost")),
        "not-accepted": _certificate(user, serial=0x9999),
        "same-serial-other-key": _certificate(user),
    }.get(case)
    header = {"no-header": None, "garbage": "not%2Ca%2Ccertificate"}.get(case, _header(presented or accepted))
    with pytest.raises(HTTPException) as raised:
        await dependencies.mtls_user(header)
    assert raised.value.status_code == 401
