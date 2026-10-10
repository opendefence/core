"""Issue and verify core API JWTs, signed ES256 with the mounted ECDSA key.

cert-manager rotates the key when it renews the Certificate and replaces the
mounted file, so the key is reloaded when the file changes. The previous key
keeps verifying tokens issued before the rotation until they expire.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey, EllipticCurvePublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

from opendefence_core.api.config import get_config
from opendefence_core.api.schema import ApiModel
from opendefence_core.models.v1alpha1 import User

ALGORITHM = "ES256"
AUDIENCE = "enrollment"


class Token(ApiModel):
    """Bearer token issued to a user."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime


class SigningKey:
    """The mounted private key, reloaded when the file changes."""

    def __init__(self) -> None:
        self._loaded: tuple[Path, int] | None = None  # path and st_mtime_ns of the loaded key
        self._key: EllipticCurvePrivateKey | None = None
        self.previous: EllipticCurvePublicKey | None = None

    def current(self) -> EllipticCurvePrivateKey:
        """Signing key, reloaded if the file changed since it was last read."""
        path = get_config().jwt_key_path
        stamp = (path, path.stat().st_mtime_ns)
        key = self._key
        if key is None or stamp != self._loaded:
            loaded = _load(path)
            if key is not None and _public_bytes(loaded) != _public_bytes(key):
                self.previous = key.public_key()
            self._key, self._loaded = loaded, stamp
            key = loaded
        return key


_signing_key = SigningKey()


def _load(path: Path) -> EllipticCurvePrivateKey:
    key = load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, EllipticCurvePrivateKey):
        raise ValueError(f"{path} is not an ECDSA private key")
    return key


def _public_bytes(key: EllipticCurvePrivateKey) -> bytes:
    return key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


def issue(user: User) -> Token:
    """Issue a token for the user."""
    if user.metadata is None or user.metadata.uid is None:
        raise ValueError("User has no uid!")
    config = get_config()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=config.jwt_lifetime)
    claims = {
        "sub": user.name,
        "uid": user.metadata.uid,
        "iss": config.jwt_issuer,
        "aud": AUDIENCE,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(claims, _signing_key.current(), algorithm=ALGORITHM)
    return Token(access_token=token, expires_at=expires_at)


def decode(token: str) -> dict[str, Any]:
    """Verify the token with the current key, or the previous one, and return its claims."""
    current = _signing_key.current().public_key()
    try:
        return _decode(token, current)
    except jwt.InvalidSignatureError:
        if _signing_key.previous is None:
            raise
        return _decode(token, _signing_key.previous)


def _decode(token: str, key: EllipticCurvePublicKey) -> dict[str, Any]:
    return jwt.decode(
        token,
        key,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=get_config().jwt_issuer,
        options={"require": ["sub", "uid", "exp"]},
    )
