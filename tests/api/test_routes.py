"""REST API endpoints, with Kubernetes access replaced by fakes."""

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.errors import APIError, ResourceNotFound
from cloudcoil.models.cert_manager.v1 import CertificateRequest, CertificateRequestStatus
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import CERTIFICATE_READY_CONDITION, Invite, User, UserStatus
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.invites import InviteNotRedeemable
from opendefence_core.api.lib.jwt import Token
from opendefence_core.api.lib.uids import compact
from opendefence_core.api.lib.users import CallsignTaken
from opendefence_core.api.routes.enrollment import views as enrollment_views
from opendefence_core.certificates import APPROVAL_ANNOTATION, certificate_identity
from tests.factories import condition, make_invite, make_user, uid

client = TestClient(app)


def _user(callsign: str = "alpha1", approved: bool = False) -> User:
    return make_user(
        callsign, callsign=callsign, approval_code="ABCD1234", approved_at=datetime.now(UTC) if approved else None
    )


def _token() -> Token:
    return Token(access_token="token", expires_at=datetime.now(UTC) + timedelta(hours=1))


@pytest.fixture
def as_user() -> Iterator[None]:
    """Authenticate requests as alpha1."""
    app.dependency_overrides[jwt_user] = lambda: _user(approved=True)
    yield
    app.dependency_overrides.clear()


def test_health() -> None:
    """The probe endpoint answers ok."""
    response = client.get("/api/v3/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthcheck() -> None:
    """The UI healthcheck reports the deployment from the domain."""
    response = client.get("/api/v3/healthcheck")
    assert response.status_code == 200
    assert response.json()["dns"] == "local-dev.opendefence.fi"
    assert response.json()["deployment"] == "local-dev"


def test_docs_under_api() -> None:
    """Docs and OpenAPI are served under /api, where Traefik routes."""
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200


@pytest.mark.parametrize(("invite", "valid"), [(make_invite(), True), (None, False)])
def test_check(monkeypatch: pytest.MonkeyPatch, invite: Invite | None, valid: bool) -> None:
    """Check reports whether the code can be redeemed."""

    async def find_invite(code: str) -> Invite | None:
        assert code == "CODE1234"
        return invite

    monkeypatch.setattr(enrollment_views, "find_invite", find_invite)
    response = client.post("/api/v3/enrollment/check", json={"code": "CODE1234"})
    assert response.status_code == 200
    assert response.json() == {"valid": valid}


def test_enroll(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enrolling returns the pending status and a token."""

    async def redeem(code: str, callsign: str) -> User:
        _ = code
        return _user(callsign)

    def issue(user: User) -> Token:
        _ = user
        return _token()

    monkeypatch.setattr(enrollment_views, "redeem", redeem)
    monkeypatch.setattr(enrollment_views, "issue", issue)
    response = client.post("/api/v3/enrollment", json={"code": "CODE1234", "callsign": "bravo2"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == {
        "id": compact(uid("bravo2")),
        "name": "bravo2",
        "callsign": "bravo2",
        "approvalCode": "ABCD1234",
        "approved": False,
        "certificateCommonName": None,
        "certificateUri": None,
    }
    assert body["token"]["accessToken"] == "token"
    assert body["token"]["tokenType"] == "Bearer"


@pytest.mark.parametrize(("error", "status"), [(InviteNotRedeemable, 404), (CallsignTaken, 409)])
def test_enroll_errors(monkeypatch: pytest.MonkeyPatch, error: type[Exception], status: int) -> None:
    """Bad codes are 404, taken callsigns 409."""

    async def redeem(code: str, callsign: str) -> User:
        raise error

    monkeypatch.setattr(enrollment_views, "redeem", redeem)
    response = client.post("/api/v3/enrollment", json={"code": "CODE1234", "callsign": "bravo2"})
    assert response.status_code == status


def test_enroll_rejects_bad_callsign() -> None:
    """Callsigns must match the User callsign pattern."""
    response = client.post("/api/v3/enrollment", json={"code": "CODE1234", "callsign": "Not Valid!"})
    assert response.status_code == 422


def test_enrollment_status_requires_token() -> None:
    """Status needs a bearer token."""
    assert client.get("/api/v3/enrollment").status_code == 401


def test_enrollment_status(as_user: None) -> None:
    """Status shows the calling user's enrollment."""
    _ = as_user
    response = client.get("/api/v3/enrollment")
    assert response.status_code == 200
    body = response.json()
    common_name, uri = certificate_identity(_user())
    assert (body["name"], body["approved"]) == ("alpha1", True)
    assert (body["certificateCommonName"], body["certificateUri"]) == (common_name, uri)
    assert common_name.startswith("local-dev#")


def _csr(user: User) -> str:
    """Valid CSR for the user's certificate identity, as a browser would build it."""
    common_name, uri = certificate_identity(user)
    request = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)]), critical=False)
        .sign(ec.generate_private_key(ec.SECP256R1()), hashes.SHA256())
    )
    return request.public_bytes(serialization.Encoding.PEM).decode()


def _as(user: User) -> None:
    app.dependency_overrides[jwt_user] = lambda: user


def _ready(user: User, ready: bool = True) -> User:
    user.status = UserStatus(conditions=[condition(CERTIFICATE_READY_CONDITION, ready, "Issued")])
    return user


def test_csr_requires_token() -> None:
    """Sending a CSR needs a bearer token."""
    assert client.post("/api/v3/certificates/csr", json={"csr": "x"}).status_code == 401


@pytest.mark.parametrize(
    ("problem", "status"), [("unapproved", 403), ("used", 409), ("identity", 400), ("garbage", 400)]
)
def test_csr_rejected(as_user: None, problem: str, status: int) -> None:
    """Unapproved users, used approvals, and CSRs for another identity are refused."""
    _ = as_user
    user = _user(approved=problem != "unapproved")
    csr = _csr(user)
    if problem == "used":
        assert user.metadata is not None and user.spec.approved_at is not None
        user.metadata.annotations = {APPROVAL_ANNOTATION: user.spec.approved_at.isoformat()}
    if problem == "identity":
        csr = _csr(_user("bravo2", approved=True))
    _as(user)
    response = client.post("/api/v3/certificates/csr", json={"csr": "not a csr" if problem == "garbage" else csr})
    assert response.status_code == status


@pytest.mark.parametrize("conflict", [None, 409, 422])
def test_csr_stored_on_the_callers_user(monkeypatch: pytest.MonkeyPatch, as_user: None, conflict: int | None) -> None:
    """A valid CSR is patched onto the token's User, also after a callsign change; races are 409."""
    _ = as_user
    user = _user(approved=True)
    user.spec.callsign = "renamed"
    _as(user)
    csr = _csr(user)
    patched: list[tuple[str | None, list[dict[str, Any]]]] = []

    async def async_patch(self: User, operations: list[dict[str, Any]]) -> User:
        if conflict:
            raise APIError("changed", status_code=conflict)
        patched.append((self.name, operations))
        return self

    monkeypatch.setattr(User, "async_patch", async_patch)
    response = client.post("/api/v3/certificates/csr", json={"csr": csr})
    if conflict:
        assert response.status_code == 409
        return
    assert response.status_code == 202
    [(name, operations)] = patched
    assert name == "alpha1"
    assert {"op": "add", "path": "/spec/certificateSigningRequest", "value": csr} in operations


@pytest.mark.parametrize("state", ["unready", "not-ready", "revoked", "missing", "pending"])
def test_pem_not_issued(monkeypatch: pytest.MonkeyPatch, as_user: None, state: str) -> None:
    """Only a certificate the operator accepted is served."""
    _ = as_user
    user = _user(approved=True)
    if state != "unready":
        _ready(user, state != "not-ready")
    if state == "revoked":
        user.spec.revoked_at = datetime.now(UTC)
    _as(user)

    async def async_get(name: str, namespace: str) -> CertificateRequest:
        if state == "missing":
            raise ResourceNotFound(f"{namespace}/{name}")
        return CertificateRequest(metadata=ObjectMeta(name=name, namespace=namespace))

    monkeypatch.setattr(CertificateRequest, "async_get", async_get)
    assert client.get("/api/v3/certificates/chain.pem").status_code == 409


def test_pem_download(monkeypatch: pytest.MonkeyPatch, as_user: None) -> None:
    """The accepted chain is served leaf first, from the token user's CertificateRequest."""
    _ = as_user
    _as(_ready(_user(approved=True)))
    seen: list[tuple[str, str]] = []

    async def async_get(name: str, namespace: str) -> CertificateRequest:
        seen.append((namespace, name))
        status = CertificateRequestStatus(
            certificate=base64.b64encode(b"leaf\n").decode(), ca=base64.b64encode(b"ca\n").decode()
        )
        return CertificateRequest(metadata=ObjectMeta(name=name, namespace=namespace), status=status)

    monkeypatch.setattr(CertificateRequest, "async_get", async_get)
    response = client.get("/api/v3/certificates/chain.pem")
    assert response.status_code == 200
    assert response.content == b"leaf\nca\n"
    assert response.headers["content-type"] == "application/x-pem-file"
    assert seen == [("opendefence-public-certs", "user-alpha1")]
