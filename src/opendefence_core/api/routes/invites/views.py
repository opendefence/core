"""Invite management endpoints."""

from cloudcoil.errors import ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.invites import (
    create_invite,
    delete_invite,
    get_invite,
    list_invites,
    unique_invite_code,
    update_invite,
)
from opendefence_core.api.routes.invites.schema import CreateInviteRequest, InviteResponse, UpdateInviteRequest

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/invites", tags=["invites"], dependencies=[Depends(jwt_user)])


@router.get("")
async def read_invites() -> list[InviteResponse]:
    """Invites an administrator can manage, auto-approving ones excluded."""
    invites = await list_invites()
    return [InviteResponse.from_resource(invite) for invite in invites]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_invite(request: CreateInviteRequest) -> InviteResponse:
    """Create an invite with a generated code."""
    code = await unique_invite_code()
    invite = await create_invite(request.to_spec(code))
    return InviteResponse.from_resource(invite)


@router.get("/{name}")
async def read_invite(name: str) -> InviteResponse:
    """Invite by resource name."""
    invite = await get_invite(name)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return InviteResponse.from_resource(invite)


@router.patch("/{name}")
async def patch_invite(name: str, request: UpdateInviteRequest) -> InviteResponse:
    """Change fields of the invite"""
    invite = await get_invite(name)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    spec = request.apply(invite.spec)
    try:
        updated = await update_invite(invite, spec)
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return InviteResponse.from_resource(updated)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_invite(name: str) -> None:
    """Delete the invite"""
    invite = await get_invite(name)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await delete_invite(invite)
