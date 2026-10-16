"""User mTLS certificates: desired cert-manager Certificate and observed leaf."""

import base64
import hashlib
from contextlib import suppress

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateSpec, IssuerRef, PrivateKey
from cloudcoil.models.kubernetes.core.v1 import Secret
from cloudcoil.resources import Resource
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from lib_opendefence_core.models.v1alpha1 import CERTIFICATE_READY_CONDITION, User
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, PUBLIC_ISSUER, user_certificate_name, user_secret_name

REVOKED_REASON = "Revoked"
PENDING_REASON = "PendingApproval"
ISSUING_REASON = "Issuing"
ISSUED_REASON = "Issued"


def wants_certificate(user: User) -> bool:
    """Whether this user should hold a certificate: approved and not revoked."""
    return user.spec.approved_at is not None and user.spec.revoked_at is None


def desired_certificate(user: User) -> Certificate:
    """Build the Certificate for this user."""
    return Certificate(
        metadata=ObjectMeta(name=user_certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE),
        spec=CertificateSpec(
            secret_name=user_secret_name(user),
            common_name=user.spec.callsign,
            duration="8760h",
            private_key=PrivateKey(algorithm="ECDSA", size=256, encoding="PKCS8", rotation_policy="Never"),
            usages=["digital signature", "content commitment", "key encipherment", "client auth"],
            issuer_ref=IssuerRef(name=PUBLIC_ISSUER, kind="ClusterIssuer", group="cert-manager.io"),
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
    if not wants_certificate(user):
        reason = REVOKED_REASON if user.spec.revoked_at else PENDING_REASON
        ctx.condition(CERTIFICATE_READY_CONDITION, False, reason=reason)
        await remove_certificate(user, ctx)
        ctx.set_status(public_key=None)
        return
    certificate = await ctx.ensure(desired_certificate(user))
    if not is_ready(certificate):
        ctx.condition(CERTIFICATE_READY_CONDITION, False, reason=ISSUING_REASON)
        return
    secret = await ctx.get(Secret, user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    ctx.set_status(public_key=public_key_fingerprint(secret))
    ctx.condition(CERTIFICATE_READY_CONDITION, True, reason=ISSUED_REASON)


async def remove_certificate(user: User, ctx: Context[User]) -> None:
    """Delete the user's Certificate, then the key pair Secret cert-manager leaves behind.

    With rotationPolicy Never, a later Certificate would reuse the key from a
    leftover Secret, so deleting it makes re-approval issue a new key.
    """
    await _delete(ctx, Certificate, user_certificate_name(user))
    await _delete(ctx, Secret, user_secret_name(user))


async def _delete[R: Resource](ctx: Context[User], resource: type[R], name: str) -> None:
    client = await ctx.client(resource)
    with suppress(ResourceNotFound):
        await client.delete(name=name, namespace=PUBLIC_CERT_NAMESPACE)
