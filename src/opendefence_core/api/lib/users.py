"""Reading and managing platform users."""

from datetime import UTC, datetime
from typing import Literal

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import User

type UserState = Literal["pending", "active", "revoked"]

logger = get_logger(__name__)


def state_of(user: User) -> UserState:
    if user.spec.revoked_at is not None:
        return "revoked"
    if user.spec.approved_at is not None:
        return "active"
    return "pending"


async def list_users(state: UserState | None = None) -> list[User]:
    """Users, or only the ones in the state."""
    users = [user async for user in await User.async_list()]
    if state is None:
        return users
    return [user for user in users if state_of(user) == state]


async def approve(user: User) -> User:
    """Approve the user"""
    user.spec.approved_at = datetime.now(UTC)
    approved = await user.async_update()
    logger.audit("User %s approved", user.name)
    return approved


async def revoke(user: User) -> User:
    """Revoke the user"""
    user.spec.revoked_at = datetime.now(UTC)
    revoked = await user.async_update()
    logger.audit("User %s revoked", user.name)
    return revoked
