"""User request and response bodies."""

from collections.abc import Mapping
from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import Group, Role, User
from lib_opendefence_core.models.v1alpha1.user import CALLSIGN_PATTERN
from opendefence_core.api.lib.roles import effective_roles
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.lib.users import UserState, state_of
from opendefence_core.api.schema import ApiModel, RoleRef


class RenameUserRequest(ApiModel):
    """Callsign to give the user."""

    callsign: str = Field(pattern=CALLSIGN_PATTERN)


class UserResponse(ApiModel):
    """User, as the platform shows them. The resource name stays internal."""

    id: str
    callsign: str
    state: UserState
    roles: list[RoleRef]
    effective_roles: list[RoleRef]
    approval_code: str | None

    @classmethod
    def from_resource(cls, user: User, roles: Mapping[str, Role], groups: Mapping[str, Group]) -> Self:
        """Response for the User resource, naming the roles it holds by id."""
        held = effective_roles(user, groups)
        return cls(
            id=id_of(user),
            callsign=user.spec.callsign,
            state=state_of(user),
            roles=RoleRef.resolve(user.spec.role_refs, roles),
            effective_roles=[RoleRef.of(roles[name]) for name in held if name in roles],
            approval_code=user.spec.approval_code,
        )
