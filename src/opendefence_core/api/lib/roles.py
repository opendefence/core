"""Reading and managing platform roles."""

from collections.abc import Mapping

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.errors import ResourceNotFound

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import API_VERSION, Group, Role, RoleSpec, User
from opendefence_core.api.lib.groups import effective_groups
from opendefence_core.api.lib.refs import names, with_ref, without_ref

logger = get_logger(__name__)


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


async def ensure_role(name: str, display_name: str) -> None:
    """Create the role unless it exists. A reference to a missing role never resolves."""
    try:
        await Role.async_get(name)
    except ResourceNotFound:
        await create_role(name, display_name)


async def delete_role(role: Role) -> None:
    """Delete the role."""
    await role.async_remove()
    logger.audit("Role %s deleted", role.name)


async def holders(name: str) -> list[User]:
    """Users that name the role directly."""
    return [user async for user in await User.async_list() if names(name, user.spec.role_refs)]


async def referrers(name: str) -> list[str]:
    """Users and groups that still name the role, as a caller can recognise them."""
    found = [f"User/{user.spec.callsign}" for user in await holders(name)]
    found += [f"Group/{group.name}" async for group in await Group.async_list() if names(name, group.spec.role_refs)]
    return sorted(found)


def effective_roles(user: User, groups: Mapping[str, Group]) -> list[str]:
    """Roles the user holds directly and roles granted by every group it is effectively in."""
    found = {ref.name for ref in user.spec.role_refs}
    for name in effective_groups(user, groups):
        found.update(ref.name for ref in groups[name].spec.role_refs)
    return sorted(found)


async def assign_role(user: User, role: str) -> User:
    """Give the role to the user directly."""
    refs = with_ref(user.spec.role_refs, role)
    if refs is None:
        return user
    user.spec.role_refs = refs
    updated = await user.async_update()
    logger.audit("User %s given role %s", user.name, role)
    return updated


async def unassign_role(user: User, role: str) -> User:
    """Take the direct role away. A group may still grant it."""
    refs = without_ref(user.spec.role_refs, role)
    if refs is None:
        return user
    user.spec.role_refs = refs
    updated = await user.async_update()
    logger.audit("User %s no longer holds role %s directly", user.name, role)
    return updated
