"""Shared bases for REST API request and response bodies."""

from typing import Self

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.lib.users import UserState, state_of


class ApiModel(BaseModel):
    """JSON body with camelCase field names."""

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)


class ErrorResponse(ApiModel):
    """Error body, same shape as FastAPI's HTTPException."""

    detail: str


class UserSummary(ApiModel):
    """User as other objects refer to them. The resource name stays internal."""

    id: str
    callsign: str
    state: UserState

    @classmethod
    def of(cls, user: User) -> Self:
        """Summary of the User resource."""
        return cls(id=id_of(user), callsign=user.spec.callsign, state=state_of(user))
