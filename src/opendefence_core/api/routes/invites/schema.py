"""Invite request and response bodies."""

from datetime import datetime
from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import Invite, InviteSpec, ObjectRef
from opendefence_core.api.lib.invites import UNLIMITED
from opendefence_core.api.schema import ApiModel


class InviteLimits(ApiModel):
    """How often and how long an invite may be redeemed."""

    use_count: int = Field(default=UNLIMITED, ge=UNLIMITED)
    valid_until: datetime | None = None


class CreateInviteRequest(InviteLimits):
    """Invite to create. The API generates the code."""

    role_refs: list[ObjectRef] = Field(default_factory=list)
    group_refs: list[ObjectRef] = Field(default_factory=list)

    def to_spec(self, code: str) -> InviteSpec:
        """InviteSpec holding the generated code."""
        return InviteSpec(
            code=code,
            role_refs=self.role_refs,
            group_refs=self.group_refs,
            use_count=self.use_count,
            valid_until=self.valid_until,
        )


class UpdateInviteRequest(InviteLimits):
    """Invite changes. Only the sent fields change."""

    def apply(self, spec: InviteSpec) -> InviteSpec:
        """InviteSpec with the sent fields replaced."""
        changes = self.model_dump(by_alias=True, exclude_unset=True)
        return InviteSpec.model_validate(spec.model_dump(by_alias=True) | changes)


class InviteResponse(ApiModel):
    """Invite as an administrator sees it, including the code."""

    name: str
    code: str
    role_refs: list[ObjectRef]
    group_refs: list[ObjectRef]
    use_count: int
    used: int
    valid_until: datetime | None
    created_at: datetime | None

    @classmethod
    def from_resource(cls, invite: Invite) -> Self:
        """Response for the Invite resource."""
        created = invite.metadata.creation_timestamp if invite.metadata else None
        return cls(
            name=invite.name or "",
            code=invite.spec.code,
            role_refs=invite.spec.role_refs,
            group_refs=invite.spec.group_refs,
            use_count=invite.spec.use_count,
            used=invite.status.used if invite.status else 0,
            valid_until=invite.spec.valid_until,
            created_at=created.root if created else None,
        )
