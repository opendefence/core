"""Group custom resource."""

from typing import Annotated

from pydantic import Field

from cloudcoil.crd import ListType, PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource

from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION, ObjectRef, PlatformStatus, ResolvedRef


class GroupSpec(BaseModel):
    """Desired identity and membership of a platform group."""

    name: str = Field(min_length=1, description="Group name.")
    display_name: Annotated[str, PrinterColumn(name="Display name")] = Field(
        min_length=1,
        alias="displayName",
        description="Human-readable name of the group.",
    )
    parent_ref: ObjectRef | None = Field(
        default=None,
        alias="parentRef",
        description="Reference to the group that contains this group; omit for a top-level group.",
    )
    manager_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="managerRefs",
        description="References to users who manage the group.",
    )
    role_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="roleRefs",
        description="References to roles assigned to the group.",
    )


class GroupStatus(PlatformStatus):
    """Resolved parent, manager, and role UIDs for a group."""

    parent: ResolvedRef | None = Field(
        default=None,
        description="Name of the parent group this group belongs to, if configured.",
    )
    managers: Annotated[list[ResolvedRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="Names and UIDs of the users who manage the group.",
    )
    roles: Annotated[list[ResolvedRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="Names and UIDs of the roles assigned to the group.",
    )


@custom_resource(
    api_version=API_VERSION,
    plural="groups",
    scope="Cluster",
    short_names=("odgroup",),
)
class Group(Resource):
    """Cluster-scoped platform group."""

    spec: GroupSpec = Field(description="Desired configuration of the group.")
    status: GroupStatus | None = Field(
        default=None,
        description="Current observed state of the group.",
    )
