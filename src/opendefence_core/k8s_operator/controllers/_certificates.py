"""One-shot user certificates from client CSRs, and the public accepted-credential projection."""

import base64
import hashlib
import json
import os
import re
from contextlib import suppress
from datetime import UTC, datetime

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context
from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.cert_manager.v1 import CertificateRequest, CertificateRequestSpec, IssuerRef
from cloudcoil.patches import diff
from cloudcoil.resources import Resource
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization

from lib_opendefence_core.models.v1alpha1 import ACCEPTED_CREDENTIALS_ANNOTATION, CERTIFICATE_READY_CONDITION, User
from opendefence_core.certificates import (
    APPROVAL_ANNOTATION,
    certificate_approval,
    certificate_identity,
    check_csr,
    wants_certificate,
)
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, PUBLIC_ISSUER, user_certificate_name

REVOKED_REASON = "Revoked"
PENDING_REASON = "PendingApproval"
AWAITING_REQUEST_REASON = "AwaitingRequest"
INVALID_REQUEST_REASON = "InvalidRequest"
ISSUING_REASON = "Issuing"
ISSUED_REASON = "Issued"
EMPTY_CREDENTIALS = '{"version":1,"accepted":[]}'


def new_request(user: User, csr: str) -> CertificateRequest:
    """One immutable signing request for the user's PEM CSR under the current approval."""
    duration = os.environ.get("USER_CERTIFICATE_DURATION", "2880h")
    if not re.fullmatch(r"[1-9][0-9]*h", duration):
        raise ValueError("USER_CERTIFICATE_DURATION must be a positive whole number of hours")
    approval = {APPROVAL_ANNOTATION: certificate_approval(user).astimezone(UTC).isoformat()}
    return CertificateRequest(
        metadata=ObjectMeta(name=user_certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE, annotations=approval),
        spec=CertificateRequestSpec(
            request=base64.b64encode(csr.encode()).decode(),
            duration=duration,
            usages=["digital signature", "client auth"],
            issuer_ref=IssuerRef(name=PUBLIC_ISSUER, kind="ClusterIssuer", group="cert-manager.io"),
        ),
    )


def public_key_fingerprint(certificate: str) -> str:
    """Keep the existing publicKey status contract: SHA-256 of the leaf SPKI, from a base64 PEM chain."""
    leaf = x509.load_pem_x509_certificates(base64.b64decode(certificate, validate=True))[0]
    return hashlib.sha256(_spki(leaf)).hexdigest()


def _spki(item: x509.Certificate | x509.CertificateSigningRequest) -> bytes:
    return item.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def accepted_credential(user: User, request: CertificateRequest) -> dict[str, str]:
    """Verify issuance against the approved request before publishing public metadata."""
    _check_owner(user, request)
    approval = certificate_approval(user).astimezone(UTC).isoformat()
    if request.metadata and (request.metadata.annotations or {}).get(APPROVAL_ANNOTATION) != approval:
        raise ValueError("Certificate material belongs to another approval")
    if request.spec is None or request.status is None or not request.status.certificate:
        raise ValueError("CertificateRequest has no issued certificate")
    chain = x509.load_pem_x509_certificates(base64.b64decode(request.status.certificate, validate=True))
    leaf = chain[0]
    csr = x509.load_pem_x509_csr(base64.b64decode(request.spec.request, validate=True))
    # The CN is fixed at issuance, so compare it with the CSR rather than the current config
    _, uri = certificate_identity(user)
    sans = list(leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
    if (
        not csr.is_signature_valid
        or _spki(leaf) != _spki(csr)
        or leaf.subject != csr.subject
        or sans != [x509.UniformResourceIdentifier(uri)]
    ):
        raise ValueError("Issued certificate does not match the approved request and identity")
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


async def _patch_user(
    user: User, ctx: Context[User], annotations: dict[str, str], *, clear_request: bool = False
) -> User:
    """Write operator annotations and optionally take the pending CSR, in one guarded patch."""
    desired = user.model_copy(deep=True)
    if desired.metadata is None:
        raise ValueError(f"User {user.name} has no metadata")
    annotations = {
        key: value
        for key, value in annotations.items()
        if value != EMPTY_CREDENTIALS or key in (desired.metadata.annotations or {})
    }
    if annotations:
        desired.metadata.annotations = {**(desired.metadata.annotations or {}), **annotations}
    if clear_request:
        desired.spec.certificate_signing_request = None
    operations = diff(user, desired)
    if not operations:
        return user
    client = await ctx.client(User)
    return await client.patch(user, operations)


async def reconcile_certificate(user: User, ctx: Context[User]) -> None:
    """Consume each approval once, for one client CSR; never regenerate missing or expired credentials."""
    if not wants_certificate(user):
        reason = REVOKED_REASON if user.spec.revoked_at else PENDING_REASON
        # Withdraw acceptance before cleanup, even if deletion later fails
        await _unavailable(user, ctx, reason, clear_request=True)
        await remove_certificate(user, ctx)
        return
    if user.metadata is None:
        raise ValueError(f"User {user.name} has no metadata")
    approved_at = certificate_approval(user)
    approval = approved_at.astimezone(UTC).isoformat()
    consumed = (user.metadata.annotations or {}).get(APPROVAL_ANNOTATION)
    pending = user.spec.certificate_signing_request
    if consumed is None or approved_at > datetime.fromisoformat(consumed):
        if pending is None:
            await _unavailable(user, ctx, AWAITING_REQUEST_REASON)
            return
        try:
            check_csr(pending.encode(), *certificate_identity(user))
        except ValueError as exc:
            await _unavailable(user, ctx, INVALID_REQUEST_REASON, message=str(exc))
            return
        request = new_request(user, pending)
        # Reserve the approval before I/O; a partial creation requires fresh approval
        user = await _patch_user(
            user,
            ctx,
            {APPROVAL_ANNOTATION: approval, ACCEPTED_CREDENTIALS_ANNOTATION: EMPTY_CREDENTIALS},
            clear_request=True,
        )
        await remove_certificate(user, ctx)
        request = await ctx.ensure(request)
    else:
        if pending is not None:
            user = await _patch_user(user, ctx, {}, clear_request=True)
        request = await _get(ctx, CertificateRequest, user_certificate_name(user))
    if request is None:
        await _unavailable(user, ctx, "FreshApprovalRequired")
        return
    await _publish(user, ctx, request)


async def _publish(user: User, ctx: Context[User], request: CertificateRequest) -> None:
    """Accept the issued certificate only once it is verified and valid now."""
    certificate = request.status.certificate if request.status else None
    ready = request.status is not None and any(
        c.type == "Ready" and c.status == "True" for c in request.status.conditions or []
    )
    if certificate is None or not ready:
        await _unavailable(user, ctx, ISSUING_REASON)
        return
    try:
        credential = accepted_credential(user, request)
    except ValueError, x509.ExtensionNotFound:
        await _unavailable(user, ctx, "InvalidCertificate")
        raise
    now = datetime.now(UTC)
    if not datetime.fromisoformat(credential["notBefore"]) <= now < datetime.fromisoformat(credential["notAfter"]):
        await _unavailable(user, ctx, "CertificateOutsideValidity")
        return
    await _patch_user(
        user,
        ctx,
        {ACCEPTED_CREDENTIALS_ANNOTATION: json.dumps({"version": 1, "accepted": [credential]}, separators=(",", ":"))},
    )
    ctx.set_status(public_key=public_key_fingerprint(certificate))
    ctx.condition(CERTIFICATE_READY_CONDITION, True, reason=ISSUED_REASON)


async def _unavailable(
    user: User, ctx: Context[User], reason: str, *, message: str = "", clear_request: bool = False
) -> None:
    await _patch_user(user, ctx, {ACCEPTED_CREDENTIALS_ANNOTATION: EMPTY_CREDENTIALS}, clear_request=clear_request)
    ctx.set_status(public_key=None)
    ctx.condition(CERTIFICATE_READY_CONDITION, False, reason=reason, message=message)


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
    """Delete the user's one-shot request; its owner reference also removes it with the User."""
    name = user_certificate_name(user)
    existing = await _get(ctx, CertificateRequest, name)
    if existing is None:
        return
    if existing.metadata is None or not existing.metadata.uid:
        raise ValueError(f"CertificateRequest {name} has no UID")
    _check_owner(user, existing)
    client = await ctx.client(CertificateRequest)
    with suppress(ResourceNotFound):
        await client.delete(name=name, namespace=PUBLIC_CERT_NAMESPACE, uid=existing.metadata.uid)
