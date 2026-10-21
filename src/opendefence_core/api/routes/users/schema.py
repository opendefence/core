"""User request and response bodies."""

from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import User
from lib_opendefence_core.models.v1alpha1.user import CALLSIGN_PATTERN
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.lib.users import UserState, state_of
from opendefence_core.api.schema import ApiModel


class RenameUserRequest(ApiModel):
    """Callsign to give the user."""

    callsign: str = Field(pattern=CALLSIGN_PATTERN)


class UserResponse(ApiModel):
    """User, as the platform shows them. The resource name stays internal."""

    id: str
    callsign: str
    state: UserState
    roles: list[str]
    approval_code: str | None

    @classmethod
    def from_resource(cls, user: User) -> Self:
        """Response for the User resource."""
        return cls(
            id=id_of(user),
            callsign=user.spec.callsign,
            state=state_of(user),
            # TODO: include the roles inherited from groups
            roles=[ref.name for ref in user.spec.role_refs],
            approval_code=user.spec.approval_code,
        )
