"""REST API building blocks: JWTs and invite redemption rules."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from lib_opendefence_core.models.v1alpha1 import Invite
from opendefence_core.api.config import get_config
from opendefence_core.api.lib import invites
from opendefence_core.api.lib import jwt as api_jwt
from opendefence_core.api.lib.codes import ALPHABET, generate_code
from tests.factories import make_invite, make_user


def _write_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    """Write the key as the Secret mount would, with a newer mtime than any earlier key."""
    previous = path.stat().st_mtime_ns if path.exists() else 0
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    mtime = max(path.stat().st_mtime_ns, previous + 1_000_000_000)
    os.utime(path, ns=(mtime, mtime))


@pytest.fixture
def jwt_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ec.EllipticCurvePrivateKey:
    """A fresh ES256 signing key in place of the mounted Secret."""
    key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "tls.key"
    _write_key(path, key)
    monkeypatch.setattr(get_config(), "jwt_key_path", path)
    monkeypatch.setattr(api_jwt, "_signing_key", api_jwt.SigningKey())
    return key


def _invite(
    *,
    resolved: bool = True,
    use_count: int = -1,
    used: int = 0,
    valid_until: datetime | None = None,
    auto_approve: bool = False,
) -> Invite:
    """An invite into group team with role user."""
    return make_invite(
        groups=["team"],
        roles=["user"],
        resolved=resolved,
        use_count=use_count,
        used=used,
        valid_until=valid_until,
        auto_approve=auto_approve,
    )


def test_generate_code() -> None:
    """Codes have the requested length and only use the code alphabet."""
    code = generate_code(12)
    assert len(code) == 12
    assert set(code) <= set(ALPHABET)


def test_jwt_round_trip(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """Issued tokens decode with the user's name and uid."""
    _ = jwt_key
    user = make_user()
    token = api_jwt.issue(user)
    claims = api_jwt.decode(token.access_token)
    assert claims["sub"] == "alpha1"
    assert user.metadata is not None
    assert claims["uid"] == user.metadata.uid
    assert claims["iss"] == get_config().jwt_issuer
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
    user = make_user()
    assert user.metadata is not None
    user.metadata.uid = None
    with pytest.raises(ValueError, match="uid"):
        api_jwt.issue(user)


def test_jwt_key_reloads_after_rotation(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """A rotated key file signs new tokens; tokens from the previous key still verify."""
    _ = jwt_key
    earlier = api_jwt.issue(make_user()).access_token
    rotated = ec.generate_private_key(ec.SECP256R1())
    _write_key(get_config().jwt_key_path, rotated)

    later = api_jwt.issue(make_user()).access_token

    assert pyjwt.decode(later, rotated.public_key(), algorithms=["ES256"], audience=api_jwt.AUDIENCE)
    assert api_jwt.decode(earlier)["sub"] == "alpha1"
    assert api_jwt.decode(later)["sub"] == "alpha1"


def test_jwt_key_rewritten_unchanged_keeps_no_previous(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """Rewriting the same key, as on a renewal without rotation, leaves nothing to fall back to."""
    api_jwt.issue(make_user())
    _write_key(get_config().jwt_key_path, jwt_key)
    api_jwt.issue(make_user())
    assert api_jwt._signing_key.previous is None


def test_jwt_rejects_non_ecdsa_key(jwt_key: ec.EllipticCurvePrivateKey) -> None:
    """The mounted key must be ECDSA."""
    _ = jwt_key
    other = ed25519.Ed25519PrivateKey.generate()
    get_config().jwt_key_path.write_bytes(
        other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    with pytest.raises(ValueError, match="not an ECDSA private key"):
        api_jwt.issue(make_user())


@pytest.mark.parametrize(
    ("invite", "redeemable"),
    [
        (_invite(), True),
        (_invite(resolved=False), False),
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
