"""Enrollment request and response bodies."""

from typing import Self

from pydantic import Field

from lib_opendefence_core.models.v1alpha1.user import CALLSIGN_PATTERN, User
from opendefence_core.api.lib.jwt import Token
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.schema import ApiModel
from opendefence_core.certificates import certificate_identity, wants_certificate


class CheckRequest(ApiModel):
    """Invite code to check."""

    code: str


class CheckResponse(ApiModel):
    """Whether the invite code can be redeemed."""

    valid: bool


class EnrollRequest(ApiModel):
    """Invite code to redeem and the callsign to take."""

    code: str
    callsign: str = Field(pattern=CALLSIGN_PATTERN)


class EnrollmentStatus(ApiModel):
    """Enrollment of the user, as shown to themselves."""

    id: str
    name: str | None
    callsign: str
    approval_code: str | None
    approved: bool
    certificate_common_name: str | None = None
    certificate_uri: str | None = None

    @classmethod
    def from_resource(cls, user: User) -> Self:
        """Enrollment status of the User resource, with the CSR identity once approved."""
        common_name, uri = certificate_identity(user) if wants_certificate(user) else (None, None)
        return cls(
            id=id_of(user),
            name=user.name,
            callsign=user.spec.callsign,
            approval_code=user.spec.approval_code,
            approved=user.spec.approved_at is not None,
            certificate_common_name=common_name,
            certificate_uri=uri,
        )


class EnrollResponse(ApiModel):
    """Enrollment of the created user and their enrollment token."""

    status: EnrollmentStatus
    token: Token
