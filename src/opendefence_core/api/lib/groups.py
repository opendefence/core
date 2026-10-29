"""Reading and managing platform groups."""

from collections.abc import Mapping

from cloudcoil.apimachinery import ObjectMeta

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import API_VERSION, Group, GroupSpec, User
from opendefence_core.api.lib.refs import names, with_ref, without_ref

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
    return [user async for user in await User.async_list() if names(name, user.spec.group_refs)]


async def add_member(user: User, name: str) -> User:
    """Put the user in the group, doing nothing if it is already there."""
    refs = with_ref(user.spec.group_refs, name)
    if refs is None:
        return user
    user.spec.group_refs = refs
    updated = await user.async_update()
    logger.audit("User %s added to group %s", user.name, name)
    return updated


async def remove_member(user: User, name: str) -> User:
    """Take the user out of the group, doing nothing if it is not in it."""
    refs = without_ref(user.spec.group_refs, name)
    if refs is None:
        return user
    user.spec.group_refs = refs
    updated = await user.async_update()
    logger.audit("User %s removed from group %s", user.name, name)
    return updated


async def managers(group: Group) -> list[User]:
    """Users the group names as managers."""
    return [user async for user in await User.async_list() if names(user.name or "", group.spec.manager_refs)]


async def grant_role(group: Group, role: str) -> Group:
    """Make the group grant the role to its effective members."""
    refs = with_ref(group.spec.role_refs, role)
    if refs is None:
        return group
    group.spec.role_refs = refs
    updated = await group.async_update()
    logger.audit("Group %s granted role %s", group.name, role)
    return updated


async def revoke_role(group: Group, role: str) -> Group:
    """Stop the group granting the role."""
    refs = without_ref(group.spec.role_refs, role)
    if refs is None:
        return group
    group.spec.role_refs = refs
    updated = await group.async_update()
    logger.audit("Group %s stopped granting role %s", group.name, role)
    return updated


async def add_manager(group: Group, user: str) -> Group:
    """Make the user a manager of the group."""
    refs = with_ref(group.spec.manager_refs, user)
    if refs is None:
        return group
    group.spec.manager_refs = refs
    updated = await group.async_update()
    logger.audit("User %s made manager of group %s", user, group.name)
    return updated


async def remove_manager(group: Group, user: str) -> Group:
    """Stop the user managing the group."""
    refs = without_ref(group.spec.manager_refs, user)
    if refs is None:
        return group
    group.spec.manager_refs = refs
    updated = await group.async_update()
    logger.audit("User %s no longer manages group %s", user, group.name)
    return updated


def effective_groups(user: User, groups: Mapping[str, Group]) -> list[str]:
    """Names of the groups the user is in, and of every ancestor of them."""
    found: list[str] = []
    for ref in user.spec.group_refs:
        name: str | None = ref.name
        while name and name in groups and name not in found:
            found.append(name)
            parent = groups[name].spec.parent_ref
            name = parent.name if parent else None
    return found
