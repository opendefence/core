"""Group management endpoints."""

from collections.abc import Awaitable

from cloudcoil.errors import APIError, ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Group
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.groups import (
    add_member,
    create_group,
    delete_group,
    list_groups,
    members,
    remove_member,
    update_group,
)
from opendefence_core.api.lib.uids import ObjectId, ids_by_name
from opendefence_core.api.lookups import group_or_404, user_or_404
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


@router.get("")
async def read_groups() -> list[GroupResponse]:
    """Groups on the platform."""
    groups = await ids_by_name(Group)
    return [GroupResponse.from_resource(group, groups) for group in await list_groups()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_group(request: CreateGroupRequest) -> GroupResponse:
    """Create a group."""
    parent = await _parent_name(request.parent_id)
    try:
        group = await _admitted(create_group(request.name, request.to_spec(parent)))
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return GroupResponse.from_resource(group, await ids_by_name(Group))


@router.get("/{group_id}")
async def read_group(group_id: ObjectId) -> GroupResponse:
    """Group by id."""
    group = await group_or_404(group_id)
    return GroupResponse.from_resource(group, await ids_by_name(Group))


@router.patch("/{group_id}")
async def patch_group(group_id: ObjectId, request: UpdateGroupRequest) -> GroupResponse:
    """Change the display name or move the group in the hierarchy."""
    group = await group_or_404(group_id)
    parent = await _parent_name(request.parent_id) if request.sends_parent() else None
    try:
        updated = await _admitted(update_group(group, request.apply(group.spec, parent)))
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return GroupResponse.from_resource(updated, await ids_by_name(Group))


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
    return UserResponse.from_resource(await add_member(user, group.name or ""))


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(group_id: ObjectId, user_id: ObjectId) -> None:
    """Take the user out of the group."""
    group = await group_or_404(group_id)
    await remove_member(await user_or_404(user_id), group.name or "")
