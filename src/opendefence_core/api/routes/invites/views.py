"""Invite management endpoints."""

from cloudcoil.errors import ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Group, Role
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.invites import (
    create_invite,
    delete_invite,
    list_invites,
    unique_invite_code,
    update_invite,
)
from opendefence_core.api.lib.uids import ObjectId, ids_by_name
from opendefence_core.api.lookups import group_or_404, invite_or_404, role_or_404
from opendefence_core.api.routes.invites.schema import CreateInviteRequest, InviteResponse, UpdateInviteRequest

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/invites", tags=["invites"], dependencies=[Depends(jwt_user)])


@router.get("")
async def read_invites() -> list[InviteResponse]:
    """Invites an administrator can manage, auto-approving ones excluded."""
    invites = await list_invites()
    roles, groups = await ids_by_name(Role), await ids_by_name(Group)
    return [InviteResponse.from_resource(invite, roles, groups) for invite in invites]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_invite(request: CreateInviteRequest) -> InviteResponse:
    """Create an invite with a generated code."""
    role_names = [(await role_or_404(role_id)).name or "" for role_id in request.role_ids]
    group_names = [(await group_or_404(group_id)).name or "" for group_id in request.group_ids]
    code = await unique_invite_code()
    invite = await create_invite(request.to_spec(code, role_names, group_names))
    roles, groups = await ids_by_name(Role), await ids_by_name(Group)
    return InviteResponse.from_resource(invite, roles, groups)


@router.get("/{invite_id}")
async def read_invite(invite_id: ObjectId) -> InviteResponse:
    """Invite by id."""
    invite = await invite_or_404(invite_id)
    roles, groups = await ids_by_name(Role), await ids_by_name(Group)
    return InviteResponse.from_resource(invite, roles, groups)


@router.patch("/{invite_id}")
async def patch_invite(invite_id: ObjectId, request: UpdateInviteRequest) -> InviteResponse:
    """Change fields of the invite"""
    invite = await invite_or_404(invite_id)
    spec = request.apply(invite.spec)
    try:
        updated = await update_invite(invite, spec)
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    roles, groups = await ids_by_name(Role), await ids_by_name(Group)
    return InviteResponse.from_resource(updated, roles, groups)


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_invite(invite_id: ObjectId) -> None:
    """Delete the invite"""
    invite = await invite_or_404(invite_id)
    await delete_invite(invite)
