"""Lookups that answer 404 when the object is missing."""

from fastapi import HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Group, Invite, Role, User
from opendefence_core.api.lib.uids import by_uid


async def user_or_404(uid: str) -> User:
    """User by id, or 404."""
    user = await by_uid(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


async def invite_or_404(uid: str) -> Invite:
    """Invite by id, or 404. Auto-approving invites are not managed through the API."""
    invite = await by_uid(Invite, uid)
    if invite is None or invite.spec.auto_approve:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return invite


async def role_or_404(uid: str) -> Role:
    """Role by id, or 404."""
    role = await by_uid(Role, uid)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return role


async def group_or_404(uid: str) -> Group:
    """Group by id, or 404."""
    group = await by_uid(Group, uid)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return group
