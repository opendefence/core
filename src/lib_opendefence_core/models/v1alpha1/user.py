"""User custom resource."""

from datetime import datetime
from typing import Annotated

from cloudcoil.crd import ListType, PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource
from pydantic import Field

from lib_opendefence_core.models.v1alpha1.common import API_VERSION, ObjectRef, PlatformStatus, ResolvedRef

BINDINGS_SYNCED_CONDITION = "BindingsSynced"
CERTIFICATE_READY_CONDITION = "CertificateReady"
ACCEPTED_CREDENTIALS_ANNOTATION = "platform.opendefence.fi/accepted-credentials"
CALLSIGN_PATTERN = r"^[a-z0-9]{3,30}$"


class BindingObservation(BaseModel):
    """A UserBinding observed for this user in an integration namespace."""

    name: str = Field(
        min_length=1,
        description="Kubernetes resource name of the UserBinding.",
    )
    namespace: str = Field(
        min_length=1,
        description="Namespace of the UserBinding, identifying the integration.",
    )
    uid: str = Field(
        min_length=1,
        description="Kubernetes UID of the UserBinding.",
    )
    synced: bool = Field(
        description="Whether the UserBinding Synced condition is True.",
    )


class UserSpec(BaseModel):
    """Desired identity of a platform user."""

    callsign: Annotated[str, PrinterColumn(name="Callsign")] = Field(
        min_length=1,
        description="Mutable callsign displayed for the user. The Kubernetes UID identifies the user.",
        pattern=CALLSIGN_PATTERN,
    )
    revoked_at: Annotated[datetime | None, PrinterColumn(name="Revoked")] = Field(
        default=None,
        alias="revokedAt",
        description="RFC 3339 timestamp when the user was revoked; omit if the user is active.",
    )
    role_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="roleRefs",
        description="References to roles assigned directly to the user.",
    )
    group_refs: Annotated[list[ObjectRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="groupRefs",
        description="References to groups the user belongs to.",
    )
    approval_code: str | None = Field(
        default=None,
        alias="approvalCode",
        description="Code shown to the enrolling user; an administrator checks it before approving the user.",
    )
    approved_at: Annotated[datetime | None, PrinterColumn(name="Approved")] = Field(
        default=None,
        alias="approvedAt",
        description="RFC 3339 timestamp of the original user approval; omit while enrollment is pending.",
    )
    certificate_approved_at: datetime | None = Field(
        default=None,
        alias="certificateApprovedAt",
        description="RFC 3339 timestamp authorizing certificate replacement. Must be later than the consumed approval.",
    )
    certificate_signing_request: str | None = Field(
        default=None,
        alias="certificateSigningRequest",
        max_length=8192,
        description=(
            "Pending PEM PKCS#10 request from the user's client. "
            "The operator consumes it once per approval and clears it."
        ),
    )


class UserStatus(PlatformStatus):
    """Observed identity material, resolved refs, and integration UserBindings."""

    public_key: str | None = Field(
        default=None,
        alias="publicKey",
        description="Public key signature of the user's mTLS certificate, observed from the cluster.",
    )
    roles: Annotated[list[ResolvedRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="Names and UIDs of the roles assigned directly to the user.",
    )
    groups: Annotated[list[ResolvedRef], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="Names and UIDs of the groups the user belongs to.",
    )
    bindings: Annotated[list[BindingObservation], ListType("map", keys=("namespace", "name"))] = Field(
        default_factory=list,
        description="UserBindings created by integrations for this user, with their sync state.",
    )


@custom_resource(
    api_version=API_VERSION,
    plural="users",
    scope="Cluster",
    short_names=("oduser",),
)
class User(Resource):
    """Cluster-scoped platform user with an immutable Kubernetes UID."""

    spec: UserSpec = Field(description="Desired configuration of the user.")
    status: UserStatus | None = Field(
        default=None,
        description="Current observed state of the user.",
    )
