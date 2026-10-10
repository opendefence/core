"""REST API endpoints, with Kubernetes access replaced by fakes."""

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.kubernetes.core.v1 import Secret
from fastapi.testclient import TestClient

from opendefence_core.api.app import app
from opendefence_core.api.lib.common.invites import CallsignTaken, InviteNotRedeemable
from opendefence_core.api.lib.common.jwt import Token
from opendefence_core.api.lib.middleware.jwt import jwt_user
from opendefence_core.api.routes.certificates import views as certificate_views
from opendefence_core.api.routes.enrollment import views as enrollment_views
from opendefence_core.k8s_operator.models.v1alpha1 import API_VERSION, Invite, User, UserSpec

client = TestClient(app)


def _user(callsign: str = "alpha1", approved: bool = False) -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=callsign, uid=f"uid-{callsign}"),
        spec=UserSpec(
            callsign=callsign,
            approval_code="ABCD1234",
            approved_at=datetime.now(UTC) if approved else None,
        ),
    )


def _token() -> Token:
    return Token(access_token="token", expires_at=datetime.now(UTC) + timedelta(hours=1))


@pytest.fixture
def as_user() -> Iterator[None]:
    """Authenticate requests as alpha1."""
    app.dependency_overrides[jwt_user] = lambda: _user(approved=True)
    yield
    app.dependency_overrides.clear()


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


@pytest.mark.parametrize(("invite", "valid"), [(object(), True), (None, False)])
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

    monkeypatch.setattr(enrollment_views, "redeem", redeem)

    def issue(user: User) -> Token:
        _ = user
        return _token()

    monkeypatch.setattr(enrollment_views, "issue", issue)
    response = client.post("/api/v3/enrollment", json={"code": "CODE1234", "callsign": "bravo2"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == {"callsign": "bravo2", "approvalCode": "ABCD1234", "approved": False}
    assert body["token"]["accessToken"] == "token"


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
    assert response.json()["approved"] is True


def test_pfx_only_own_certificate(as_user: None) -> None:
    """Users can't download another user's certificate."""
    _ = as_user
    assert client.get("/api/v3/certificates/bravo2.pfx").status_code == 403


def test_pfx_not_issued(monkeypatch: pytest.MonkeyPatch, as_user: None) -> None:
    """Missing certificate Secrets are 409."""
    _ = as_user

    async def async_get(name: str, namespace: str) -> Secret:
        raise ResourceNotFound(f"{namespace}/{name}")

    monkeypatch.setattr(Secret, "async_get", async_get)
    assert client.get("/api/v3/certificates/alpha1.pfx").status_code == 409


def test_pfx_download(monkeypatch: pytest.MonkeyPatch, as_user: None) -> None:
    """Issued certificates download as a .pfx named after the callsign and deployment."""
    _ = as_user
    seen: list[tuple[str, str]] = []

    async def async_get(name: str, namespace: str) -> Secret:
        seen.append((namespace, name))
        data = {"tls.key": base64.b64encode(b"key").decode(), "tls.crt": base64.b64encode(b"crt").decode()}
        return Secret(metadata=ObjectMeta(name=name, namespace=namespace), data=data)

    monkeypatch.setattr(Secret, "async_get", async_get)

    def build_pfx(callsign: str, key: bytes, chain: bytes) -> bytes:
        _ = callsign
        return b"pfx:" + key + chain

    monkeypatch.setattr(certificate_views, "build_pfx", build_pfx)
    response = client.get("/api/v3/certificates/alpha1.pfx")
    assert response.status_code == 200
    assert response.content == b"pfx:keycrt"
    assert seen == [("opendefence-public-certs", "user-alpha1")]
    assert 'filename="alpha1_local-dev.pfx"' in response.headers["content-disposition"]
