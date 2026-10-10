"""User mTLS certificates: desired cert-manager Certificate and observed leaf."""

import base64
import hashlib

from cloudcoil.controller import Context
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateSpec, IssuerRef, PrivateKey
from cloudcoil.models.kubernetes.core.v1 import Secret
from cloudcoil.apimachinery import ObjectMeta
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from opendefence_core.k8s_operator.models.v1alpha1 import User
from opendefence_core.k8s_operator.models.v1alpha1.user import CERTIFICATE_READY_CONDITION

PUBLIC_CERT_NAMESPACE = "opendefence-public-certs"
PUBLIC_CERT_ISSUER = "public-issuer"

REVOKED_REASON = "Revoked"
PENDING_REASON = "PendingApproval"
ISSUING_REASON = "Issuing"
ISSUED_REASON = "Issued"


def certificate_name(user: User) -> str:
    """Name of the Certificate for this user."""
    return f"user-{user.name}"


def secret_name(user: User) -> str:
    """Name of the Secret cert-manager writes the key pair to."""
    return f"user-{user.name}"


def wants_certificate(user: User) -> bool:
    """Whether this user should hold a certificate: approved and not revoked."""
    return user.spec.approved_at is not None and user.spec.revoked_at is None


def desired_certificate(user: User) -> Certificate:
    """Build the Certificate for this user."""
    return Certificate(
        metadata=ObjectMeta(name=certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE),
        spec=CertificateSpec(
            secret_name=secret_name(user),
            common_name=user.spec.callsign,
            duration="8760h",
            private_key=PrivateKey(algorithm="ECDSA", size=256, encoding="PKCS8", rotation_policy="Never"),
            usages=["digital signature", "content commitment", "key encipherment", "client auth"],
            issuer_ref=IssuerRef(name=PUBLIC_CERT_ISSUER, kind="ClusterIssuer", group="cert-manager.io"),
        ),
    )


def is_ready(certificate: Certificate) -> bool:
    """Whether cert-manager reports the Certificate Ready=True."""
    status = certificate.status
    generation = certificate.metadata.generation if certificate.metadata else None
    return any(
        c.type == "Ready" and c.status == "True" and c.observed_generation == generation
        for c in (status.conditions or [] if status else [])
    )


def public_key_fingerprint(secret: Secret) -> str:
    """SHA-256 fingerprint of the leaf's (first cert in tls.crt) public key."""
    data = secret.data or {}
    if "tls.crt" not in data:
        raise ValueError(f"Secret {secret.name} has no tls.crt")
    leaf = x509.load_pem_x509_certificates(base64.b64decode(data["tls.crt"]))[0]
    spki = leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).hexdigest()


async def reconcile_certificate(user: User, ctx: Context[User]) -> None:
    """Ensure or remove the user's Certificate and record it in status."""
    if wants_certificate(user=user):
        # User is recently created, or certificate creation is pending
        certificate = await ctx.ensure(desired_certificate(user=user))
        if not is_ready(certificate=certificate):
            ctx.condition(CERTIFICATE_READY_CONDITION, False, reason=ISSUING_REASON)
            return
        else:
            secret = await ctx.get(resource=Secret, name=secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
            ctx.set_status(public_key=public_key_fingerprint(secret=secret))
            ctx.condition(CERTIFICATE_READY_CONDITION, True, reason=ISSUED_REASON)
    else:
        # User is revoked
        ctx.condition(
            CERTIFICATE_READY_CONDITION, False, reason=REVOKED_REASON if user.spec.revoked_at else PENDING_REASON
        )
        client = await ctx.client(Certificate)
        try:
            await client.delete(name=certificate_name(user=user), namespace=PUBLIC_CERT_NAMESPACE)
        except ResourceNotFound:
            pass
        ctx.set_status(public_key=None)
