"""FastAPI dependencies shared by the routes."""

from typing import Annotated

import jwt
from cloudcoil.errors import ResourceNotFound
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.lib.jwt import decode
from opendefence_core.api.lib.mtls import CLIENT_CERT_HEADER, certificate_user, leaf_certificate

bearer = HTTPBearer(auto_error=False)
ClientCertificateHeader = Annotated[str | None, Header(alias=CLIENT_CERT_HEADER, include_in_schema=False)]


async def _user_from_token(token: str) -> User | None:
    try:
        claims = decode(token)
        user = await User.async_get(claims["sub"])
    except jwt.InvalidTokenError, ResourceNotFound:
        return None
    # A User recreated under the same name is a different user
    if user.metadata is None or user.metadata.uid != claims["uid"] or user.spec.revoked_at:
        return None
    return user


async def jwt_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    """User the enrollment token was issued to; 401 unless it is valid and the user is not revoked."""
    user = await _user_from_token(credentials.credentials) if credentials else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return user


JWTUser = Annotated[User, Depends(jwt_user)]


async def mtls_user(header: ClientCertificateHeader = None) -> User:
    """User whose client certificate was passed from the proxy; 401 unless that certificate is still accepted."""
    if not header:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    try:
        leaf = leaf_certificate(header)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED) from exc
    user = await certificate_user(leaf)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return user


MTLSUser = Annotated[User, Depends(mtls_user)]
