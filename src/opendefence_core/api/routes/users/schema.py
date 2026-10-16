"""User request and response bodies."""

from typing import Self

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.lib.users import UserState, state_of
from opendefence_core.api.schema import ApiModel


class UserResponse(ApiModel):
    """User, as the platform shows them."""

    name: str
    callsign: str
    state: UserState
    roles: list[str]
    approval_code: str | None

    @classmethod
    def from_resource(cls, user: User) -> Self:
        """Response for the User resource."""
        return cls(
            name=user.name or "",
            callsign=user.spec.callsign,
            state=state_of(user),
            # TODO: include the roles inherited from groups
            roles=[ref.name for ref in user.spec.role_refs],
            approval_code=user.spec.approval_code,
        )
