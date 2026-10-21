"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from opendefence_core.api.dependencies import JWTUser, jwt_user
from opendefence_core.api.lib.uids import ObjectId
from opendefence_core.api.lib.users import (
    CallsignTaken,
    UserState,
    approve,
    check_callsign,
    list_users,
    rename,
    revoke,
)
from opendefence_core.api.lookups import user_or_404
from opendefence_core.api.routes.users.schema import RenameUserRequest, UserResponse

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


@router.get("/{user_id}")
async def read_user(user_id: ObjectId) -> UserResponse:
    """User by id."""
    return UserResponse.from_resource(await user_or_404(user_id))


@router.patch("/{user_id}")
async def rename_user(user_id: ObjectId, request: RenameUserRequest) -> UserResponse:
    """Change the user's callsign."""
    user = await user_or_404(user_id)
    if user.spec.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A revoked user cannot be renamed.")
    try:
        await check_callsign(request.callsign, excluding=user.name)
    except CallsignTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="The callsign is taken.") from exc
    renamed = await rename(user, request.callsign)
    return UserResponse.from_resource(renamed)


@router.post("/{user_id}/approve")
async def approve_user(user_id: ObjectId) -> UserResponse:
    """Approve the user"""
    user = await user_or_404(user_id)
    return UserResponse.from_resource(await approve(user))


@router.post("/{user_id}/revoke")
async def revoke_user(user_id: ObjectId, caller: JWTUser) -> UserResponse:
    """Revoke the user"""
    user = await user_or_404(user_id)
    if caller.metadata is not None and caller.metadata.uid == user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You cannot revoke yourself.")
    return UserResponse.from_resource(await revoke(user))
