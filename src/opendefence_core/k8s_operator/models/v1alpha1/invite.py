"""Invite custom resource."""

from datetime import datetime
from typing import Annotated

from pydantic import Field

from cloudcoil.crd import ListType, PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource

from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION, ObjectRef, PlatformStatus


class InviteSpec(BaseModel):
    """Desired grants and limits of a platform invite."""

    code: str = Field(min_length=1, description="Invite redemption code.")
    group_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="groupRefs",
        description="References to groups the invited user will join.",
    )
    role_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="roleRefs",
        description="References to roles assigned when the invite is redeemed.",
    )
    use_count: Annotated[int, PrinterColumn(name="Uses")] = Field(
        default=-1,
        ge=-1,
        alias="useCount",
        description="Number of times the invite may be redeemed; -1 allows unlimited uses.",
    )
    valid_until: Annotated[datetime | None, PrinterColumn(name="Valid until")] = Field(
        default=None,
        alias="validUntil",
        description=("RFC 3339 timestamp after which the invite can no longer be redeemed; omit for no expiration."),
    )
    auto_approve: bool = Field(
        default=False,
        alias="autoApprove",
        description="Whether users created from this invite are approved automatically.",
    )


class InviteStatus(PlatformStatus):
    """Current reconciliation state of an invite."""

    used: Annotated[int, PrinterColumn(name="Used")] = Field(
        default=0,
        ge=0,
        description="Number of times the invite has been redeemed.",
    )


@custom_resource(
    api_version=API_VERSION,
    plural="invites",
    scope="Cluster",
    short_names=("odinvite",),
)
class Invite(Resource):
    """Cluster-scoped platform invite."""

    spec: InviteSpec = Field(description="Desired configuration of the invite.")
    status: InviteStatus | None = Field(
        default=None,
        description="Current observed state of the invite.",
    )
