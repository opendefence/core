"""Issue and verify core API JWTs, signed ES256 with the mounted ECDSA key."""

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from pydantic import Field

from cloudcoil.pydantic import BaseModel

from opendefence_core.api.config import config
from opendefence_core.k8s_operator.models.v1alpha1.user import User

ALGORITHM = "ES256"
AUDIENCE = "enrollment"


class Token(BaseModel):
    """Bearer token issued to a user."""

    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_at: datetime = Field(alias="expiresAt")


@cache
def _private_key() -> EllipticCurvePrivateKey:
    key = load_pem_private_key(config.jwt_key_path.read_bytes(), password=None)
    if not isinstance(key, EllipticCurvePrivateKey):
        raise ValueError(f"{config.jwt_key_path} is not an ECDSA private key")
    return key


def issue(user: User) -> Token:
    """Issue a token for the user."""
    if user.metadata is None or user.metadata.uid is None:
        raise ValueError("User has no uid!")
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
    token = jwt.encode(claims, _private_key(), algorithm=ALGORITHM)
    return Token(access_token=token, expires_at=expires_at)


def decode(token: str) -> dict[str, Any]:
    """Verify the token and return its claims"""
    return jwt.decode(
        token,
        _private_key().public_key(),
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=config.jwt_issuer,
        options={"require": ["sub", "uid", "exp"]},
    )
