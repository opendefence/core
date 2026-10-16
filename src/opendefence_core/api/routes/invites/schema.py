"""Invite request and response bodies."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1 import Invite, InviteSpec, ObjectRef
from opendefence_core.api.lib.invites import UNLIMITED
from opendefence_core.api.lib.uids import RefId, id_of
from opendefence_core.api.schema import ApiModel


class InviteLimits(ApiModel):
    """How often and how long an invite may be redeemed."""

    use_count: int = Field(default=UNLIMITED, ge=UNLIMITED)
    valid_until: datetime | None = None


class CreateInviteRequest(InviteLimits):
    """Invite to create. The API generates the code."""

    role_ids: list[RefId] = Field(default_factory=list)
    group_ids: list[RefId] = Field(default_factory=list)

    def to_spec(self, code: str, roles: Sequence[str], groups: Sequence[str]) -> InviteSpec:
        """InviteSpec holding the generated code and the resolved reference names."""
        return InviteSpec(
            code=code,
            role_refs=[ObjectRef(name=name) for name in roles],
            group_refs=[ObjectRef(name=name) for name in groups],
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

    id: str
    code: str
    role_ids: list[str]
    group_ids: list[str]
    use_count: int
    used: int
    valid_until: datetime | None
    created_at: datetime | None

    @classmethod
    def from_resource(cls, invite: Invite, roles: Mapping[str, str], groups: Mapping[str, str]) -> Self:
        """Response for the Invite resource, naming its references by id."""
        created = invite.metadata.creation_timestamp if invite.metadata else None
        return cls(
            id=id_of(invite),
            code=invite.spec.code,
            role_ids=_ids(invite.spec.role_refs, roles),
            group_ids=_ids(invite.spec.group_refs, groups),
            use_count=invite.spec.use_count,
            used=invite.status.used if invite.status else 0,
            valid_until=invite.spec.valid_until,
            created_at=created.root if created else None,
        )


def _ids(refs: Sequence[ObjectRef], ids: Mapping[str, str]) -> list[str]:
    """Ids of the referenced objects that exist; the operator reports the rest."""
    return [ids[ref.name] for ref in refs if ref.name in ids]
