"""Serial number -> certificate status from the Users' accepted credentials."""

from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography import x509
from cryptography.x509 import ocsp

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.certificates import accepted_entry

NOT_ISSUED_TIME = datetime(1970, 1, 1, tzinfo=UTC)
"""revocationTime of a serial with no record, under the RFC 6960 2.2 extended revoked definition."""


@dataclass
class CertStatusResult:
    """Verdict for a single serial"""

    status: ocsp.OCSPCertStatus
    revocation_time: datetime | None = None  # required when REVOKED
    revocation_reason: x509.ReasonFlags | None = None


async def lookup_status(serial: int, responder_serial: int) -> CertStatusResult:
    """Good for an accepted credential or the responder itself; every other serial of the CA is revoked"""
    if serial == responder_serial:
        return CertStatusResult(status=ocsp.OCSPCertStatus.GOOD)
    now = datetime.now(UTC)
    async for user in await User.async_list():
        if accepted_entry(user, serial, now):
            return CertStatusResult(status=ocsp.OCSPCertStatus.GOOD)
    # Revocation removes the accepted record, so a revoked serial looks like one never issued
    return CertStatusResult(
        status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=NOT_ISSUED_TIME,
        revocation_reason=x509.ReasonFlags.certificate_hold,
    )
