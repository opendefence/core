"""Reading and managing platform roles."""

from collections.abc import Sequence

from cloudcoil.apimachinery import ObjectMeta

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import API_VERSION, Group, ObjectRef, Role, RoleSpec, User

logger = get_logger(__name__)


def _names(name: str, refs: Sequence[ObjectRef]) -> bool:
    return any(ref.name == name for ref in refs)


def is_managed(role: Role) -> bool:
    """Whether an Integration owns the role."""
    owners = role.metadata.owner_references if role.metadata else None
    return any(ref.kind == "Integration" and ref.controller for ref in owners or [])


async def list_roles() -> list[Role]:
    """Every role."""
    return [role async for role in await Role.async_list()]


async def create_role(name: str, display_name: str) -> Role:
    """Create a role."""
    role = Role(
        api_version=API_VERSION,
        kind="Role",
        metadata=ObjectMeta(name=name),
        spec=RoleSpec(display_name=display_name),
    )
    created = await role.async_create()
    logger.audit("Role %s created", created.name)
    return created


async def delete_role(role: Role) -> None:
    """Delete the role."""
    await role.async_remove()
    logger.audit("Role %s deleted", role.name)


async def holders(name: str) -> list[User]:
    """Users that name the role directly."""
    return [user async for user in await User.async_list() if _names(name, user.spec.role_refs)]


async def referrers(name: str) -> list[str]:
    """Users and groups that still name the role, as a caller can recognise them."""
    found = [f"User/{user.spec.callsign}" for user in await holders(name)]
    found += [f"Group/{group.name}" async for group in await Group.async_list() if _names(name, group.spec.role_refs)]
    return sorted(found)
