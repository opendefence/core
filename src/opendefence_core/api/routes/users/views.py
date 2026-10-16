"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from opendefence_core.api.dependencies import JWTUser, jwt_user
from opendefence_core.api.lib.uids import ObjectId
from opendefence_core.api.lib.users import UserState, approve, list_users, revoke
from opendefence_core.api.lookups import user_or_404
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


@router.get("/{user_id}")
async def read_user(user_id: ObjectId) -> UserResponse:
    """User by id."""
    return UserResponse.from_resource(await user_or_404(user_id))


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
