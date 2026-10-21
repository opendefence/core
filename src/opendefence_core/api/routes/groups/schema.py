"""Group request and response bodies."""

from collections.abc import Mapping
from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import Group, GroupSpec, ObjectRef
from lib_opendefence_core.models.v1alpha1.integration import ROLE_NAME_PATTERN
from opendefence_core.api.lib.uids import RefId, id_of
from opendefence_core.api.schema import ApiModel


class CreateGroupRequest(ApiModel):
    """Group to create."""

    name: str = Field(max_length=63, pattern=ROLE_NAME_PATTERN)
    display_name: str = Field(min_length=1)
    parent_id: RefId | None = None

    def to_spec(self, parent: str | None) -> GroupSpec:
        """GroupSpec for the new group, under the resolved parent name."""
        return GroupSpec(
            display_name=self.display_name,
            parent_ref=ObjectRef(name=parent) if parent else None,
        )


class UpdateGroupRequest(ApiModel):
    """Group changes. Only the sent fields change."""

    display_name: str | None = Field(default=None, min_length=1)
    parent_id: RefId | None = None

    def sends_parent(self) -> bool:
        """Whether the caller asked to move the group, including to the root."""
        return "parent_id" in self.model_fields_set

    def apply(self, spec: GroupSpec, parent: str | None) -> GroupSpec:
        """GroupSpec with the sent fields replaced, under the resolved parent name."""
        updated = spec.model_copy(deep=True)
        if self.display_name is not None:
            updated.display_name = self.display_name
        if self.sends_parent():
            updated.parent_ref = ObjectRef(name=parent) if parent else None
        return updated


class GroupResponse(ApiModel):
    """Group, as the platform shows it. The name is the slug the caller chose."""

    id: str
    name: str
    display_name: str
    parent_id: str | None
    roles: list[str]
    managers: list[str]

    @classmethod
    def from_resource(cls, group: Group, groups: Mapping[str, str]) -> Self:
        """Response for the Group resource, naming its parent by id."""
        parent = group.spec.parent_ref
        return cls(
            id=id_of(group),
            name=group.name or "",
            display_name=group.spec.display_name,
            parent_id=groups.get(parent.name) if parent else None,
            roles=[ref.name for ref in group.spec.role_refs],
            managers=[ref.name for ref in group.spec.manager_refs],
        )
