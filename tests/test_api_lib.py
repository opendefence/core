"""REST API building blocks: JWTs, .pfx bundles, invite redemption rules."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt as pyjwt
import pytest
from cloudcoil.apimachinery import ObjectMeta
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from opendefence_core.api.config import config
from opendefence_core.api.lib.certificates.pfx import build_pfx
from opendefence_core.api.lib.common import invites
from opendefence_core.api.lib.common import jwt as api_jwt
from opendefence_core.api.lib.common.codes import ALPHABET, generate_code
from opendefence_core.k8s_operator.models.v1alpha1 import API_VERSION, Invite, InviteSpec, InviteStatus, User, UserSpec
from opendefence_core.k8s_operator.models.v1alpha1.common import ObjectRef, PlatformCondition


@pytest.fixture
def jwt_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ec.EllipticCurvePrivateKey]:
    """A fresh ES256 signing key in place of the mounted Secret."""
    key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "tls.key"
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    monkeypatch.setattr(config, "jwt_key_path", path)
    api_jwt._private_key.cache_clear()
    yield key
    api_jwt._private_key.cache_clear()


def _user(name: str = "alpha1", uid: str | None = "uid-alpha1") -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, uid=uid),
        spec=UserSpec(callsign=name),
    )


def _invite(
    *,
    ready: bool = True,
    use_count: int = -1,
    used: int = 0,
    valid_until: datetime | None = None,
    auto_approve: bool = False,
) -> Invite:
    conditions = [
        PlatformCondition(
            last_transition_time="2026-09-13T00:00:00Z",
            message="",
            reason="Resolved" if ready else "MissingReference",
            status="True" if ready else "False",
            type="ReferencesResolved",
        )
    ]
    return Invite(
        api_version=API_VERSION,
        kind="Invite",
        metadata=ObjectMeta(name="invite"),
        spec=InviteSpec(
            code="CODE1234",
            group_refs=[ObjectRef(name="team")],
            role_refs=[ObjectRef(name="user")],
            use_count=use_count,
            valid_until=valid_until,
            auto_approve=auto_approve,
        ),
        status=InviteStatus(conditions=conditions, used=used),
    )


def test_generate_code() -> None:
    """Codes have the requested length and only use the code alphabet."""
    code = generate_code(12)
    assert len(code) == 12
    assert set(code) <= set(ALPHABET)


def test_jwt_round_trip(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """Issued tokens decode with the user's name and uid."""
    _ = jwt_key
    token = api_jwt.issue(_user())
    claims = api_jwt.decode(token.access_token)
    assert claims["sub"] == "alpha1"
    assert claims["uid"] == "uid-alpha1"
    assert claims["iss"] == config.jwt_issuer
    assert token.expires_at > datetime.now(UTC)


def test_jwt_rejects_other_keys(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """Tokens signed with another key don't verify."""
    _ = jwt_key
    other = ec.generate_private_key(ec.SECP256R1())
    forged = pyjwt.encode(
        {"sub": "alpha1", "uid": "x", "exp": datetime.now(UTC) + timedelta(hours=1)}, other, algorithm="ES256"
    )
    with pytest.raises(pyjwt.InvalidTokenError):
        api_jwt.decode(forged)


def test_jwt_requires_uid(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """A user without a uid can't be issued a token."""
    _ = jwt_key
    with pytest.raises(ValueError, match="uid"):
        api_jwt.issue(_user(uid=None))


def test_build_pfx_round_trip() -> None:
    """The .pfx opens with the callsign and holds the key and certificate."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "alpha1")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    chain_pem = certificate.public_bytes(serialization.Encoding.PEM)
    loaded_key, loaded_cert, _ = pkcs12.load_key_and_certificates(build_pfx("alpha1", key_pem, chain_pem), b"alpha1")
    assert loaded_cert == certificate
    assert loaded_key is not None


@pytest.mark.parametrize(
    ("invite", "redeemable"),
    [
        (_invite(), True),
        (_invite(ready=False), False),
        (_invite(use_count=2, used=1), True),
        (_invite(use_count=2, used=2), False),
        (_invite(valid_until=datetime.now(UTC) + timedelta(days=1)), True),
        (_invite(valid_until=datetime.now(UTC) - timedelta(days=1)), False),
    ],
)
def test_invite_redeemable(invite: Invite, redeemable: bool) -> None:
    """Invites must be resolved, unexpired, and have uses left."""
    assert invites._is_redeemable(invite) is redeemable


def test_new_user_from_invite() -> None:
    """Users inherit the invite's refs and get an approval code."""
    user = invites._new_user(_invite(), "bravo2")
    assert user.name == "bravo2"
    assert user.spec.callsign == "bravo2"
    assert [ref.name for ref in user.spec.group_refs] == ["team"]
    assert [ref.name for ref in user.spec.role_refs] == ["user"]
    assert user.spec.approval_code is not None
    assert len(user.spec.approval_code) == invites.APPROVAL_CODE_LENGTH
    assert user.spec.approved_at is None


def test_new_user_auto_approved() -> None:
    """Auto-approving invites approve the user right away."""
    user = invites._new_user(_invite(auto_approve=True), "bravo2")
    assert user.spec.approved_at is not None
