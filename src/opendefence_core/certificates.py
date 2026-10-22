"""User certificate rules shared by the operator and the REST API."""

import hashlib
from datetime import datetime
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.config import get_config

APPROVAL_ANNOTATION = "platform.opendefence.fi/certificate-approval"


def wants_certificate(user: User) -> bool:
    """Whether this user is approved and not revoked."""
    return user.spec.approved_at is not None and user.spec.revoked_at is None


def certificate_approval(user: User) -> datetime:
    """Use enrollment once; only a fresh certificate approval can advance issuance."""
    if user.spec.approved_at is None:
        raise ValueError(f"User {user.name} is not approved")
    consumed = (user.metadata.annotations or {}).get(APPROVAL_ANNOTATION) if user.metadata else None
    baseline = datetime.fromisoformat(consumed) if consumed else user.spec.approved_at
    return max(baseline, user.spec.certificate_approved_at or baseline)


def approval_used(user: User) -> bool:
    """Whether the current approval has already authorized an issuance."""
    consumed = (user.metadata.annotations or {}).get(APPROVAL_ANNOTATION) if user.metadata else None
    return consumed is not None and certificate_approval(user) <= datetime.fromisoformat(consumed)


def certificate_identity(user: User) -> tuple[str, str]:
    """Use the canonical Kubernetes UID; callsign changes do not change identity."""
    if user.metadata is None or user.metadata.uid is None:
        raise ValueError(f"User {user.name} has no UID; only stored Users get certificates")
    uid = str(UUID(user.metadata.uid))
    tag = hashlib.sha256(uid.encode()).hexdigest()[:8]
    return f"{get_config().deployment}#{tag}", f"urn:uuid:{uid}"


def check_csr(pem: bytes, common_name: str, uri: str) -> x509.CertificateSigningRequest:
    """Accept only a self-signed P-256 request for exactly this identity, with no other extensions."""
    try:
        csr = x509.load_pem_x509_csr(pem)
        extensions = list(csr.extensions)
    except (ValueError, x509.DuplicateExtension) as exc:
        raise ValueError("Certificate request is not a valid PEM PKCS#10 request") from exc
    key = csr.public_key()
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Certificate request key must be ECDSA P-256")
    if not csr.is_signature_valid:
        raise ValueError("Certificate request signature is not valid")
    if csr.subject != x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]):
        raise ValueError(f"Certificate request subject must be CN={common_name}")
    wanted = x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)])
    if [extension.value for extension in extensions] != [wanted]:
        raise ValueError(f"Certificate request must contain only the subjectAltName URI {uri}")
    return csr
