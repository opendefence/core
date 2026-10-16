"""Reading platform users."""

from typing import Literal

from cloudcoil.errors import ResourceNotFound

from lib_opendefence_core.models.v1alpha1 import User

type UserState = Literal["pending", "active", "revoked"]


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


async def get_user(callsign: str) -> User | None:
    """User by callsign."""
    try:
        return await User.async_get(callsign)
    except ResourceNotFound:
        return None
