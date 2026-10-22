"""One-shot user certificates and the public accepted-credential projection."""

import base64
import hashlib
import json
import os
import re
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateRequest, CertificateRequestSpec, IssuerRef
from cloudcoil.models.kubernetes.core.v1 import Secret
from cloudcoil.patches import diff
from cloudcoil.resources import Resource
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lib_opendefence_core.models.v1alpha1 import ACCEPTED_CREDENTIALS_ANNOTATION, CERTIFICATE_READY_CONDITION, User
from opendefence_core.certificates import (
    APPROVAL_ANNOTATION,
    certificate_approval,
    certificate_identity,
    wants_certificate,
)
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, PUBLIC_ISSUER, user_certificate_name, user_secret_name

REVOKED_REASON = "Revoked"
PENDING_REASON = "PendingApproval"
ISSUING_REASON = "Issuing"
ISSUED_REASON = "Issued"
EMPTY_CREDENTIALS = '{"version":1,"accepted":[]}'


def new_request(user: User) -> tuple[Secret, CertificateRequest]:
    """Generate one key and one immutable signing request for a fresh approval."""
    duration = os.environ.get("USER_CERTIFICATE_DURATION", "2880h")
    if not re.fullmatch(r"[1-9][0-9]*h", duration):
        raise ValueError("USER_CERTIFICATE_DURATION must be a positive whole number of hours")
    common_name, uri = certificate_identity(user)
    approval = {APPROVAL_ANNOTATION: certificate_approval(user).astimezone(UTC).isoformat()}
    key = ec.generate_private_key(ec.SECP256R1())
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    secret = Secret(
        metadata=ObjectMeta(name=user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE, annotations=approval),
        data={
            "tls.key": base64.b64encode(
                key.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                )
            ).decode()
        },
    )
    request = CertificateRequest(
        metadata=ObjectMeta(name=user_certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE, annotations=approval),
        spec=CertificateRequestSpec(
            request=base64.b64encode(csr.public_bytes(serialization.Encoding.PEM)).decode(),
            duration=duration,
            usages=["digital signature", "client auth"],
            issuer_ref=IssuerRef(name=PUBLIC_ISSUER, kind="ClusterIssuer", group="cert-manager.io"),
        ),
    )
    return secret, request


def public_key_fingerprint(secret: Secret) -> str:
    """Keep the existing publicKey status contract: SHA-256 of the leaf SPKI."""
    if not secret.data or "tls.crt" not in secret.data:
        raise ValueError(f"Secret {secret.name} has no tls.crt")
    leaf = x509.load_pem_x509_certificates(base64.b64decode(secret.data["tls.crt"], validate=True))[0]
    return hashlib.sha256(_spki(leaf)).hexdigest()


def _spki(certificate: x509.Certificate) -> bytes:
    return certificate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def accepted_credential(user: User, request: CertificateRequest, secret: Secret) -> dict[str, str]:
    """Verify issuance against the approved request before publishing public metadata."""
    approval = certificate_approval(user).astimezone(UTC).isoformat()
    for resource in (request, secret):
        _check_owner(user, resource)
        if resource.metadata and (resource.metadata.annotations or {}).get(APPROVAL_ANNOTATION) != approval:
            raise ValueError("Certificate material belongs to another approval")
    if request.spec is None or request.status is None or not request.status.certificate:
        raise ValueError("CertificateRequest has no issued certificate")
    chain = x509.load_pem_x509_certificates(base64.b64decode(request.status.certificate, validate=True))
    leaf = chain[0]
    csr = x509.load_pem_x509_csr(base64.b64decode(request.spec.request, validate=True))
    key = serialization.load_pem_private_key(base64.b64decode((secret.data or {})["tls.key"], validate=True), None)
    key_spki = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    csr_spki = csr.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    # The deployment label is an issuance-time snapshot, so compare with the CSR.
    uri = f"urn:uuid:{UUID(user.metadata.uid if user.metadata and user.metadata.uid else '')}"
    sans = list(leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
    if (
        not csr.is_signature_valid
        or _spki(leaf) != key_spki
        or _spki(leaf) != csr_spki
        or leaf.subject != csr.subject
        or sans != [x509.UniformResourceIdentifier(uri)]
    ):
        raise ValueError("Issued certificate does not match the approved key and identity")
    issuers = chain[1:]
    if request.status.ca:
        issuers.extend(x509.load_pem_x509_certificates(base64.b64decode(request.status.ca, validate=True)))
    for issuer in issuers:
        try:
            leaf.verify_directly_issued_by(issuer)
        except ValueError, TypeError, InvalidSignature:
            continue
        return {
            "fingerprintSha256": leaf.fingerprint(hashes.SHA256()).hex(),
            "serial": format(leaf.serial_number, "x"),
            "issuerId": f"sha256:{hashlib.sha256(_spki(issuer)).hexdigest()}",
            "notBefore": leaf.not_valid_before_utc.isoformat(),
            "notAfter": leaf.not_valid_after_utc.isoformat(),
        }
    raise ValueError("Issued certificate has no verifiable issuing CA")


async def _annotate(user: User, ctx: Context[User], values: dict[str, str]) -> User:
    desired = user.model_copy(deep=True)
    assert desired.metadata is not None
    values = {
        key: value
        for key, value in values.items()
        if value != EMPTY_CREDENTIALS or key in (desired.metadata.annotations or {})
    }
    if not values:
        return user
    desired.metadata.annotations = {**(desired.metadata.annotations or {}), **values}
    operations = diff(user, desired)
    if not operations:
        return user
    client = await ctx.client(User)
    return await client.patch(user, operations)


async def reconcile_certificate(user: User, ctx: Context[User]) -> None:
    """Consume each approval once; never regenerate missing or expired credentials."""
    if not wants_certificate(user):
        reason = REVOKED_REASON if user.spec.revoked_at else PENDING_REASON
        # Withdraw acceptance before cleanup, even if deletion later fails.
        await _unavailable(user, ctx, reason)
        await remove_certificate(user, ctx)
        return
    assert user.spec.approved_at is not None and user.metadata is not None
    approved_at = certificate_approval(user)
    approval = approved_at.astimezone(UTC).isoformat()
    consumed = (user.metadata.annotations or {}).get(APPROVAL_ANNOTATION)
    if await _get(ctx, Certificate, user_certificate_name(user)) is not None:
        # Stop renewal without silently replacing legacy callsign certificates.
        await _annotate(user, ctx, {APPROVAL_ANNOTATION: approval, ACCEPTED_CREDENTIALS_ANNOTATION: EMPTY_CREDENTIALS})
        await remove_certificate(user, ctx)
        ctx.set_status(public_key=None)
        ctx.condition(CERTIFICATE_READY_CONDITION, False, reason="FreshApprovalRequired")
        return
    if consumed is None or approved_at > datetime.fromisoformat(consumed):
        secret, request = new_request(user)
        # Reserve approval before I/O. A partial creation requires fresh approval.
        user = await _annotate(
            user, ctx, {APPROVAL_ANNOTATION: approval, ACCEPTED_CREDENTIALS_ANNOTATION: EMPTY_CREDENTIALS}
        )
        await remove_certificate(user, ctx)
        await ctx.ensure(secret)
        request = await ctx.ensure(request)
    else:
        request = await _get(ctx, CertificateRequest, user_certificate_name(user))
    secret = await _get(ctx, Secret, user_secret_name(user))
    if request is None or secret is None:
        await _unavailable(user, ctx, "FreshApprovalRequired")
        return
    if not request.status or not any(c.type == "Ready" and c.status == "True" for c in request.status.conditions or []):
        await _unavailable(user, ctx, ISSUING_REASON)
        return
    try:
        credential = accepted_credential(user, request, secret)
    except ValueError, KeyError, x509.ExtensionNotFound:
        await _unavailable(user, ctx, "InvalidCertificate")
        raise
    now = datetime.now(UTC)
    if not datetime.fromisoformat(credential["notBefore"]) <= now < datetime.fromisoformat(credential["notAfter"]):
        await _unavailable(user, ctx, "CertificateOutsideValidity")
        return
    assert request.status.certificate is not None
    data = {**(secret.data or {}), "tls.crt": request.status.certificate}
    if request.status.ca:
        data["ca.crt"] = request.status.ca
    secret = await ctx.ensure(
        Secret(
            metadata=ObjectMeta(name=secret.name, namespace=PUBLIC_CERT_NAMESPACE), type="kubernetes.io/tls", data=data
        )
    )
    await _annotate(
        user,
        ctx,
        {ACCEPTED_CREDENTIALS_ANNOTATION: json.dumps({"version": 1, "accepted": [credential]}, separators=(",", ":"))},
    )
    ctx.set_status(public_key=public_key_fingerprint(secret))
    ctx.condition(CERTIFICATE_READY_CONDITION, True, reason=ISSUED_REASON)


async def _unavailable(user: User, ctx: Context[User], reason: str) -> None:
    await _annotate(user, ctx, {ACCEPTED_CREDENTIALS_ANNOTATION: EMPTY_CREDENTIALS})
    ctx.set_status(public_key=None)
    ctx.condition(CERTIFICATE_READY_CONDITION, False, reason=reason)


def _check_owner(user: User, resource: Resource) -> None:
    if (
        not resource.metadata
        or not user.metadata
        or not any(
            ref.controller and ref.kind == "User" and ref.uid == user.metadata.uid
            for ref in resource.metadata.owner_references or []
        )
    ):
        raise ValueError(f"Refusing unrelated {resource.kind} {resource.name}")


async def _get[R: Resource](ctx: Context[User], resource: type[R], name: str) -> R | None:
    try:
        return await ctx.get(resource, name, namespace=PUBLIC_CERT_NAMESPACE)
    except ResourceNotFound:
        return None


async def remove_certificate(user: User, ctx: Context[User]) -> None:
    """Delete legacy renewal resources, one-shot requests, and private material."""
    for resource, name in (
        (Certificate, user_certificate_name(user)),
        (CertificateRequest, user_certificate_name(user)),
        (Secret, user_secret_name(user)),
    ):
        existing = await _get(ctx, resource, name)
        if existing is None:
            continue
        assert existing.metadata is not None and existing.metadata.uid
        # Legacy cert-manager Secrets did not have an owner reference.
        if resource is not Secret or existing.metadata.owner_references:
            _check_owner(user, existing)
        client = await ctx.client(resource)
        with suppress(ResourceNotFound):
            await client.delete(name=name, namespace=PUBLIC_CERT_NAMESPACE, uid=existing.metadata.uid)
