"""Role management endpoints."""

from cloudcoil.errors import ResourceConflict
from fastapi import APIRouter, Depends, HTTPException, status

from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.roles import create_role, delete_role, holders, is_managed, list_roles, referrers
from opendefence_core.api.lib.uids import ObjectId
from opendefence_core.api.lookups import role_or_404
from opendefence_core.api.routes.roles.schema import CreateRoleRequest, RoleResponse
from opendefence_core.api.schema import UserSummary

# FIXME: switch to the mTLS user with the superadmin role
router = APIRouter(prefix="/roles", tags=["roles"], dependencies=[Depends(jwt_user)])

MANAGED_MESSAGE = "An integration owns this role."


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


@router.get("/{role_id}")
async def read_role(role_id: ObjectId) -> RoleResponse:
    """Role by id."""
    return RoleResponse.from_resource(await role_or_404(role_id))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(role_id: ObjectId) -> None:
    """Delete the role."""
    role = await role_or_404(role_id)
    if is_managed(role):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=MANAGED_MESSAGE)
    referring = await referrers(role.name or "")
    if referring:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Role is still named by: {', '.join(referring)}")
    await delete_role(role)


@router.get("/{role_id}/members")
async def read_role_members(role_id: ObjectId) -> list[UserSummary]:
    """Users that name the role directly."""
    role = await role_or_404(role_id)
    return [UserSummary.of(user) for user in await holders(role.name or "")]
