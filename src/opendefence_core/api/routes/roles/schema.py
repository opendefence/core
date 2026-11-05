"""Role request and response bodies."""

from datetime import datetime
from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import Role
from lib_opendefence_core.models.v1alpha1.integration import ROLE_NAME_PATTERN
from opendefence_core.api.lib.roles import is_managed
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.schema import ApiModel


class CreateRoleRequest(ApiModel):
    """Role to create."""

    name: str = Field(max_length=63, pattern=ROLE_NAME_PATTERN)
    display_name: str = Field(min_length=1)


class RoleResponse(ApiModel):
    """Role, as the platform shows it. The name is the slug the caller chose."""

    id: str
    name: str
    display_name: str
    managed: bool
    created_at: datetime | None

    @classmethod
    def from_resource(cls, role: Role) -> Self:
        """Response for the Role resource."""
        created = role.metadata.creation_timestamp if role.metadata else None
        return cls(
            id=id_of(role),
            name=role.name or "",
            display_name=role.spec.display_name,
            managed=is_managed(role),
            created_at=created.root if created else None,
        )
