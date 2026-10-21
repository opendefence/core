"""Shared bases for REST API request and response bodies."""

from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from lib_opendefence_core.models.v1alpha1 import Group, ObjectRef, Role, User
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

    @classmethod
    def resolve(cls, refs: Sequence[ObjectRef], users: Mapping[str, User]) -> list[Self]:
        """References the platform can resolve; the operator reports the rest."""
        return [cls.of(users[ref.name]) for ref in refs if ref.name in users]


class RoleRef(ApiModel):
    """Role as other objects refer to it."""

    id: str
    name: str
    display_name: str

    @classmethod
    def of(cls, role: Role) -> Self:
        """Reference to the Role resource."""
        return cls(id=id_of(role), name=role.name or "", display_name=role.spec.display_name)

    @classmethod
    def resolve(cls, refs: Sequence[ObjectRef], roles: Mapping[str, Role]) -> list[Self]:
        """References the platform can resolve; the operator reports the rest."""
        return [cls.of(roles[ref.name]) for ref in refs if ref.name in roles]


class GroupRef(ApiModel):
    """Group as other objects refer to it, with its place in the hierarchy."""

    id: str
    name: str
    display_name: str
    parent_id: str | None

    @classmethod
    def of(cls, group: Group, groups: Mapping[str, Group]) -> Self:
        """Reference to the Group resource, naming its parent by id."""
        parent = group.spec.parent_ref
        target = groups.get(parent.name) if parent else None
        return cls(
            id=id_of(group),
            name=group.name or "",
            display_name=group.spec.display_name,
            parent_id=id_of(target) if target else None,
        )

    @classmethod
    def resolve(cls, refs: Sequence[ObjectRef], groups: Mapping[str, Group]) -> list[Self]:
        """References the platform can resolve; the operator reports the rest."""
        return [cls.of(groups[ref.name], groups) for ref in refs if ref.name in groups]
