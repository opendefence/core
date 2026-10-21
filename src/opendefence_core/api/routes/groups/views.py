"""Group management endpoints."""

from collections.abc import Awaitable

from cloudcoil.errors import APIError, ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Group, Role, User
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.groups import (
    add_manager,
    add_member,
    create_group,
    delete_group,
    grant_role,
    list_groups,
    members,
    remove_manager,
    remove_member,
    revoke_role,
    update_group,
)
from opendefence_core.api.lib.uids import ObjectId, by_name
from opendefence_core.api.lookups import group_or_404, role_or_404, user_or_404
from opendefence_core.api.routes.groups.schema import CreateGroupRequest, GroupResponse, UpdateGroupRequest
from opendefence_core.api.routes.users.schema import UserResponse
from opendefence_core.api.schema import UserSummary

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(jwt_user)])


async def _admitted[T](write: Awaitable[T]) -> T:
    """Report an operator admission denial, such as a parent cycle, as a conflict."""
    try:
        return await write
    except ResourceConflict:
        raise
    except APIError as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise


async def _parent_name(parent_id: str | None) -> str | None:
    """Resource name of the parent the caller named by id, or None for a root group."""
    return (await group_or_404(parent_id)).name if parent_id else None


async def _response(group: Group) -> GroupResponse:
    """Group response with everything it references resolved to ids."""
    return GroupResponse.from_resource(group, await by_name(Group), await by_name(Role), await by_name(User))


@router.get("")
async def read_groups() -> list[GroupResponse]:
    """Groups on the platform."""
    groups, roles, users = await by_name(Group), await by_name(Role), await by_name(User)
    return [GroupResponse.from_resource(group, groups, roles, users) for group in await list_groups()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_group(request: CreateGroupRequest) -> GroupResponse:
    """Create a group."""
    parent = await _parent_name(request.parent_id)
    try:
        group = await _admitted(create_group(request.name, request.to_spec(parent)))
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return await _response(group)


@router.get("/{group_id}")
async def read_group(group_id: ObjectId) -> GroupResponse:
    """Group by id."""
    return await _response(await group_or_404(group_id))


@router.patch("/{group_id}")
async def patch_group(group_id: ObjectId, request: UpdateGroupRequest) -> GroupResponse:
    """Change the display name or move the group in the hierarchy."""
    group = await group_or_404(group_id)
    parent = await _parent_name(request.parent_id) if request.sends_parent() else None
    try:
        updated = await _admitted(update_group(group, request.apply(group.spec, parent)))
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return await _response(updated)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group(group_id: ObjectId) -> None:
    """Delete a group that has no child groups."""
    await _admitted(delete_group(await group_or_404(group_id)))


@router.get("/{group_id}/members")
async def read_group_members(group_id: ObjectId) -> list[UserSummary]:
    """Users that name the group directly."""
    group = await group_or_404(group_id)
    return [UserSummary.of(user) for user in await members(group.name or "")]


@router.put("/{group_id}/members/{user_id}")
async def add_group_member(group_id: ObjectId, user_id: ObjectId) -> UserResponse:
    """Put the user in the group."""
    group = await group_or_404(group_id)
    user = await user_or_404(user_id)
    return UserResponse.from_resource(await add_member(user, group.name or ""), await by_name(Role))


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(group_id: ObjectId, user_id: ObjectId) -> None:
    """Take the user out of the group."""
    group = await group_or_404(group_id)
    await remove_member(await user_or_404(user_id), group.name or "")


@router.put("/{group_id}/roles/{role_id}")
async def grant_group_role(group_id: ObjectId, role_id: ObjectId) -> GroupResponse:
    """Make the group grant the role to its effective members."""
    group = await group_or_404(group_id)
    role = await role_or_404(role_id)
    return await _response(await _admitted(grant_role(group, role.name or "")))


@router.delete("/{group_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_group_role(group_id: ObjectId, role_id: ObjectId) -> None:
    """Stop the group granting the role."""
    group = await group_or_404(group_id)
    role = await role_or_404(role_id)
    await _admitted(revoke_role(group, role.name or ""))


@router.put("/{group_id}/managers/{user_id}")
async def add_group_manager(group_id: ObjectId, user_id: ObjectId) -> GroupResponse:
    """Make the user a manager of the group."""
    group = await group_or_404(group_id)
    user = await user_or_404(user_id)
    return await _response(await _admitted(add_manager(group, user.name or "")))


@router.delete("/{group_id}/managers/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_manager(group_id: ObjectId, user_id: ObjectId) -> None:
    """Stop the user managing the group."""
    group = await group_or_404(group_id)
    user = await user_or_404(user_id)
    await _admitted(remove_manager(group, user.name or ""))
