"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from opendefence_core.api.dependencies import JWTUser, jwt_user
from opendefence_core.api.lib.users import UserState, approve, get_user, list_users, revoke
from opendefence_core.api.routes.users.schema import UserResponse

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(jwt_user)])


@router.get("/me")
async def read_me(user: JWTUser) -> UserResponse:
    """The calling user."""
    return UserResponse.from_resource(user)


@router.get("")
async def read_users(state: UserState | None = None) -> list[UserResponse]:
    """Users on the platform by state"""
    users = await list_users(state)
    return [UserResponse.from_resource(user) for user in users]


@router.get("/{callsign}")
async def read_user(callsign: str) -> UserResponse:
    """User by callsign."""
    user = await get_user(callsign)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return UserResponse.from_resource(user)


@router.post("/{callsign}/approve")
async def approve_user(callsign: str) -> UserResponse:
    """Approve the user"""
    user = await get_user(callsign)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    approved = await approve(user)
    return UserResponse.from_resource(approved)


@router.post("/{callsign}/revoke")
async def revoke_user(callsign: str, caller: JWTUser) -> UserResponse:
    """Revoke the user"""
    user = await get_user(callsign)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if caller.name == callsign:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You cannot revoke yourself.")
    revoked = await revoke(user)
    return UserResponse.from_resource(revoked)
