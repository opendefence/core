"""Role management endpoints."""

from cloudcoil.errors import ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from lib_opendefence_core.models.v1alpha1 import Role
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.roles import (
    create_role,
    delete_role,
    get_role,
    holders,
    is_managed,
    list_roles,
    referrers,
)
from opendefence_core.api.routes.roles.schema import CreateRoleRequest, RoleResponse
from opendefence_core.api.routes.users.schema import UserResponse

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/roles", tags=["roles"], dependencies=[Depends(jwt_user)])

MANAGED_MESSAGE = "An integration owns this role."


async def _role(name: str) -> Role:
    role = await get_role(name)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return role


@router.get("")
async def read_roles() -> list[RoleResponse]:
    """Roles on the platform."""
    return [RoleResponse.from_resource(role) for role in await list_roles()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_role(request: CreateRoleRequest) -> RoleResponse:
    """Create a role."""
    try:
        role = await create_role(request.name, request.display_name)
    except ResourceConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return RoleResponse.from_resource(role)


@router.get("/{name}")
async def read_role(name: str) -> RoleResponse:
    """Role by name."""
    return RoleResponse.from_resource(await _role(name))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(name: str) -> None:
    """Delete the role."""
    role = await _role(name)
    if is_managed(role):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=MANAGED_MESSAGE)
    referring = await referrers(name)
    if referring:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Role is still named by: {', '.join(referring)}")
    await delete_role(role)


@router.get("/{name}/members")
async def read_role_members(name: str) -> list[UserResponse]:
    """Users that name the role directly."""
    await _role(name)
    return [UserResponse.from_resource(user) for user in await holders(name)]
