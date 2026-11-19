"""RFC 6960 OCSP responder core: DER request in, DER response out."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509 import ocsp
from cryptography.x509.oid import ObjectIdentifier

from lib_opendefence_core.logging import get_logger
from opendefence_core.api.routes.certificates.ocsp.signer import get_signer
from opendefence_core.api.routes.certificates.ocsp.status import lookup_status

logger = get_logger(__name__)

MAX_NONCE_BYTES = 32  # RFC 8954
RESPONSE_VALIDITY = timedelta(minutes=10)
EXTENDED_REVOKE = x509.UnrecognizedExtension(ObjectIdentifier("1.3.6.1.5.5.7.48.1.9"), b"\x05\x00")
"""RFC 6960 4.4.8: "revoked" also covers serials never issued."""


@dataclass
class ResponseMeta:
    success: bool
    nonce: bool = False
    this_update: datetime | None = None
    next_update: datetime | None = None


def unsuccessful(status: ocsp.OCSPResponseStatus) -> tuple[bytes, ResponseMeta]:
    """Build an unsigned OCSP error response"""
    der = ocsp.OCSPResponseBuilder.build_unsuccessful(status).public_bytes(serialization.Encoding.DER)
    return der, ResponseMeta(success=False)


async def build_ocsp_response(der: bytes) -> tuple[bytes, ResponseMeta]:
    """Handle one OCSP request; never raises, errors become OCSP error responses"""
    try:
        req = ocsp.load_der_ocsp_request(der)
    except ValueError, NotImplementedError:  # NotImplementedError: more than one request
        return unsuccessful(ocsp.OCSPResponseStatus.MALFORMED_REQUEST)

    try:
        material = get_signer()
        algkey = req.hash_algorithm.name
        if algkey not in material.name_hashes:
            return unsuccessful(ocsp.OCSPResponseStatus.UNAUTHORIZED)
        if req.issuer_name_hash != material.name_hashes[algkey] or req.issuer_key_hash != material.key_hashes[algkey]:
            return unsuccessful(ocsp.OCSPResponseStatus.UNAUTHORIZED)

        result = await lookup_status(req.serial_number, material.cert.serial_number)

        now = datetime.now(UTC)
        this_update = now - timedelta(seconds=60)
        next_update = now + RESPONSE_VALIDITY
        builder = (
            ocsp.OCSPResponseBuilder()
            .add_response_by_hash(
                issuer_name_hash=req.issuer_name_hash,
                issuer_key_hash=req.issuer_key_hash,
                algorithm=req.hash_algorithm,
                serial_number=req.serial_number,
                cert_status=result.status,
                this_update=this_update,
                next_update=next_update,
                revocation_time=result.revocation_time,
                revocation_reason=result.revocation_reason,
            )
            .responder_id(ocsp.OCSPResponderEncoding.HASH, material.cert)
            .certificates([material.cert])
            .add_extension(EXTENDED_REVOKE, critical=False)
        )

        has_nonce = False
        try:
            ext = req.extensions.get_extension_for_class(x509.OCSPNonce)
            if len(ext.value.nonce) > MAX_NONCE_BYTES:
                return unsuccessful(ocsp.OCSPResponseStatus.MALFORMED_REQUEST)
            builder = builder.add_extension(x509.OCSPNonce(ext.value.nonce), critical=False)
            has_nonce = True
        except x509.ExtensionNotFound:
            pass

        resp_der = builder.sign(material.key, hashes.SHA256()).public_bytes(encoding=serialization.Encoding.DER)
        return resp_der, ResponseMeta(
            success=True,
            nonce=has_nonce,
            this_update=this_update,
            next_update=next_update,
        )

    except Exception:
        logger.exception("OCSP response building failed")
        return unsuccessful(ocsp.OCSPResponseStatus.INTERNAL_ERROR)
