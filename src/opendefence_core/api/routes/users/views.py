"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Group, Role
from opendefence_core.api.dependencies import JWTUser, jwt_user
from opendefence_core.api.lib.groups import effective_groups
from opendefence_core.api.lib.roles import assign_role, effective_roles, unassign_role
from opendefence_core.api.lib.uids import ObjectId, by_name
from opendefence_core.api.lib.users import (
    CallsignTaken,
    UserState,
    approve,
    check_callsign,
    list_users,
    rename,
    revoke,
)
from opendefence_core.api.lookups import role_or_404, user_or_404
from opendefence_core.api.routes.users.schema import RenameUserRequest, UserResponse
from opendefence_core.api.schema import GroupRef, RoleRef

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(jwt_user)])


@router.get("/me")
async def read_me(user: JWTUser) -> UserResponse:
    """The calling user."""
    return UserResponse.from_resource(user, await by_name(Role), await by_name(Group))


@router.get("")
async def read_users(state: UserState | None = None) -> list[UserResponse]:
    """Users on the platform by state"""
    users = await list_users(state)
    roles, groups = await by_name(Role), await by_name(Group)
    return [UserResponse.from_resource(user, roles, groups) for user in users]


@router.get("/{user_id}")
async def read_user(user_id: ObjectId) -> UserResponse:
    """User by id."""
    user = await user_or_404(user_id)
    return UserResponse.from_resource(user, await by_name(Role), await by_name(Group))


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
    return UserResponse.from_resource(renamed, await by_name(Role), await by_name(Group))


@router.get("/{user_id}/roles")
async def read_user_roles(user_id: ObjectId, effective: bool = False) -> list[RoleRef]:
    """Roles held directly, or every role once group grants are counted."""
    user = await user_or_404(user_id)
    roles = await by_name(Role)
    if not effective:
        return RoleRef.resolve(user.spec.role_refs, roles)
    held = effective_roles(user, await by_name(Group))
    return [RoleRef.of(roles[name]) for name in held if name in roles]


@router.put("/{user_id}/roles/{role_id}")
async def give_user_role(user_id: ObjectId, role_id: ObjectId) -> UserResponse:
    """Give the role to the user directly."""
    user = await user_or_404(user_id)
    role = await role_or_404(role_id)
    assigned = await assign_role(user, role.name or "")
    return UserResponse.from_resource(assigned, await by_name(Role), await by_name(Group))


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def take_user_role(user_id: ObjectId, role_id: ObjectId) -> None:
    """Take the direct role away. A group may still grant it."""
    user = await user_or_404(user_id)
    role = await role_or_404(role_id)
    await unassign_role(user, role.name or "")


@router.get("/{user_id}/groups")
async def read_user_groups(user_id: ObjectId, effective: bool = False) -> list[GroupRef]:
    """Groups joined directly, or those plus every ancestor of them."""
    user = await user_or_404(user_id)
    groups = await by_name(Group)
    if not effective:
        return GroupRef.resolve(user.spec.group_refs, groups)
    return [GroupRef.of(groups[name], groups) for name in effective_groups(user, groups)]


@router.post("/{user_id}/approve")
async def approve_user(user_id: ObjectId) -> UserResponse:
    """Approve the user"""
    user = await user_or_404(user_id)
    return UserResponse.from_resource(await approve(user), await by_name(Role), await by_name(Group))


@router.post("/{user_id}/revoke")
async def revoke_user(user_id: ObjectId, caller: JWTUser) -> UserResponse:
    """Revoke the user"""
    user = await user_or_404(user_id)
    if caller.metadata is not None and caller.metadata.uid == user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You cannot revoke yourself.")
    return UserResponse.from_resource(await revoke(user), await by_name(Role), await by_name(Group))
