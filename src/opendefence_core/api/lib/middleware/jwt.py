"""Resolve the calling user from an enrollment JWT."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cloudcoil.errors import ResourceNotFound

from opendefence_core.api.lib.common.jwt import decode
from opendefence_core.k8s_operator.models.v1alpha1.user import User

bearer = HTTPBearer(auto_error=False)


async def _user_from_token(token: str) -> User | None:
    try:
        claims = decode(token)
        user = await User.async_get(claims["sub"])
    except jwt.InvalidTokenError, ResourceNotFound:
        return None
    if user.metadata is None or user.metadata.uid != claims["uid"] or user.spec.revoked_at:
        return None
    return user


async def jwt_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    """User the enrollment token was issued to."""
    user = await _user_from_token(credentials.credentials) if credentials else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return user


JWTUser = Annotated[User, Depends(jwt_user)]
