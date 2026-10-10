"""Role custom resource."""

from typing import Annotated

from pydantic import Field

from cloudcoil.crd import PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource

from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION, PlatformStatus


class RoleSpec(BaseModel):
    """Desired identity of a platform role."""

    name: str = Field(min_length=1, description="Role name.")
    display_name: Annotated[str, PrinterColumn(name="Display name")] = Field(
        min_length=1,
        alias="displayName",
        description="Human-readable name of the role.",
    )


class RoleStatus(PlatformStatus):
    """Ready conditions for a role. Roles have no outgoing references."""


@custom_resource(
    api_version=API_VERSION,
    plural="roles",
    scope="Cluster",
    short_names=("odrole",),
)
class Role(Resource):
    """Cluster-scoped platform role."""

    spec: RoleSpec = Field(description="Desired configuration of the role.")
    status: RoleStatus | None = Field(
        default=None,
        description="Current observed state of the role.",
    )
