"""Reading and managing platform groups."""

from cloudcoil.apimachinery import ObjectMeta

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import API_VERSION, Group, GroupSpec, ObjectRef, User

logger = get_logger(__name__)


async def list_groups() -> list[Group]:
    """Every group."""
    return [group async for group in await Group.async_list()]


async def create_group(name: str, spec: GroupSpec) -> Group:
    """Create a group."""
    group = Group(api_version=API_VERSION, kind="Group", metadata=ObjectMeta(name=name), spec=spec)
    created = await group.async_create()
    logger.audit("Group %s created", created.name)
    return created


async def update_group(group: Group, spec: GroupSpec) -> Group:
    """Replace the group spec, failing on a concurrent change."""
    group.spec = spec
    return await group.async_update()


async def delete_group(group: Group) -> None:
    """Delete the group."""
    await group.async_remove()
    logger.audit("Group %s deleted", group.name)


async def members(name: str) -> list[User]:
    """Users that name the group directly."""
    return [user async for user in await User.async_list() if _names(name, user.spec.group_refs)]


async def add_member(user: User, name: str) -> User:
    """Put the user in the group, doing nothing if it is already there."""
    if _names(name, user.spec.group_refs):
        return user
    user.spec.group_refs.append(ObjectRef(name=name))
    updated = await user.async_update()
    logger.audit("User %s added to group %s", user.name, name)
    return updated


async def remove_member(user: User, name: str) -> User:
    """Take the user out of the group, doing nothing if it is not in it."""
    if not _names(name, user.spec.group_refs):
        return user
    user.spec.group_refs = [ref for ref in user.spec.group_refs if ref.name != name]
    updated = await user.async_update()
    logger.audit("User %s removed from group %s", user.name, name)
    return updated


def _names(name: str, refs: list[ObjectRef]) -> bool:
    return any(ref.name == name for ref in refs)
