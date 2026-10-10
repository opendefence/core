"""UserBinding custom resource."""

from pydantic import Field

from cloudcoil.crd import PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource

from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION, ObjectRef, PlatformStatus

SYNCED_CONDITION = "Synced"


class UserBindingSpec(BaseModel):
    """Desired link from an integration to a platform user."""

    user_ref: ObjectRef = Field(
        alias="userRef",
        description="Reference to the cluster-scoped User this integration is provisioning.",
    )


class UserBindingStatus(PlatformStatus):
    """Synchronization conditions reported by the integrating controller."""


@custom_resource(
    api_version=API_VERSION,
    plural="userbindings",
    scope="Namespaced",
    short_names=("odub",),
    columns=(
        PrinterColumn(name="User", json_path=".spec.userRef.name"),
        PrinterColumn(
            name="Synced",
            json_path='.status.conditions[?(@.type=="Synced")].status',
        ),
        PrinterColumn(name="Age", json_path=".metadata.creationTimestamp", type="date"),
    ),
)
class UserBinding(Resource):
    """Namespaced record that an integration has taken a User into account.

    Integrations create one UserBinding per User in their own namespace and set
    the Synced status condition when provisioning for that User is complete.
    This operator watches UserBindings; it does not admit or reconcile them.
    """

    spec: UserBindingSpec = Field(description="Desired configuration of the user binding.")
    status: UserBindingStatus | None = Field(
        default=None,
        description="Current observed state of the user binding.",
    )


def is_synced(binding: UserBinding) -> bool:
    """Return True when the integration has reported the Synced condition as True."""
    status = binding.status
    if status is None:
        return False
    return any(condition.type == SYNCED_CONDITION and condition.status == "True" for condition in status.conditions)
