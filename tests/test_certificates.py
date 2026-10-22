"""One-shot issuance, approval consumption, identity, publication, and cleanup."""

import base64
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from cloudcoil.apimachinery import ObjectMeta, OwnerReference
from cloudcoil.controller import Context, Wait
from cloudcoil.errors import ResourceConflict
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateRequest, CertificateRequestStatus, Condition
from cloudcoil.models.kubernetes.core.v1 import Secret
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from pydantic import ValidationError

from lib_opendefence_core.models.v1alpha1 import ACCEPTED_CREDENTIALS_ANNOTATION, CERTIFICATE_READY_CONDITION, User
from opendefence_core.certificates import APPROVAL_ANNOTATION, certificate_identity, check_csr, wants_certificate
from opendefence_core.config import Config
from opendefence_core.k8s_operator.controllers._certificates import (
    EMPTY_CREDENTIALS,
    accepted_credential,
    new_request,
    public_key_fingerprint,
    reconcile_certificate,
)
from opendefence_core.k8s_operator.controllers.users import finalize_user, reconcile_user
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, PUBLIC_ISSUER, user_certificate_name, user_secret_name
from tests.factories import make_user
from tests.fakes import FakeClient, FakeContext


def _context(user: User) -> FakeContext:
    return FakeContext(clients={User: FakeClient([user])}, parent=user)


async def _current(ctx: FakeContext) -> User:
    assert ctx.parent is not None
    return await ctx.get(User, ctx.parent.name or "")


async def _reconcile(ctx: FakeContext) -> None:
    await reconcile_certificate(await _current(ctx), cast(Context[User], ctx))


async def _issued(ctx: FakeContext, *, expired: bool = False) -> CertificateRequest:
    """Simulate the CA signing the exact CSR and returning its issuer certificate."""
    user = await _current(ctx)
    request = await ctx.get(CertificateRequest, user_certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    assert request.spec is not None
    csr = x509.load_pem_x509_csr(base64.b64decode(request.spec.request))
    ca_key = ec.generate_private_key(ec.SECP256R1())
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")])
    now = datetime.now(UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    leaf = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(issuer)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now + timedelta(days=-1 if expired else 120))
        .add_extension(csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value, critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    request.status = CertificateRequestStatus(
        certificate=base64.b64encode(leaf.public_bytes(serialization.Encoding.PEM)).decode(),
        ca=base64.b64encode(ca.public_bytes(serialization.Encoding.PEM)).decode(),
        conditions=[Condition(type="Ready", status="True")],
    )
    return request


def test_identity_and_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only immutable UID enters the SAN/tag; settings are snapshotted in the CSR."""
    user = make_user(approved_at=datetime.now(UTC))
    secret, request = new_request(user)
    assert secret.name == user_secret_name(user)
    assert request.name == user_certificate_name(user)
    assert request.spec is not None
    assert request.spec.duration == "2880h"
    assert request.spec.issuer_ref.name == PUBLIC_ISSUER
    assert request.spec.usages == ["digital signature", "client auth"]
    common_name, uri = certificate_identity(user)
    assert user.metadata is not None and user.metadata.uid is not None
    assert common_name == f"local-dev#{hashlib.sha256(user.metadata.uid.encode()).hexdigest()[:8]}"
    assert uri == f"urn:uuid:{user.metadata.uid}"
    user.spec.callsign = "renamed"
    assert certificate_identity(user) == (common_name, uri)
    _deployment(monkeypatch, "another-deployment")
    monkeypatch.setenv("USER_CERTIFICATE_DURATION", "1440h")
    _, changed = new_request(user)
    assert changed.spec is not None and changed.spec.duration == "1440h"
    assert certificate_identity(user)[0].startswith("another-deployment#")


def _deployment(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Use another deployment name in the certificate CN for this test."""
    config = Config(domain=f"{name}.opendefence.fi", deployment=name)
    monkeypatch.setattr("opendefence_core.certificates.get_config", lambda: config)


@pytest.mark.parametrize("duration", ["0h", "-1h", "4months", "", "1s"])
def test_invalid_duration(duration: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_CERTIFICATE_DURATION", duration)
    with pytest.raises(ValueError, match="whole number of hours"):
        new_request(make_user())


def test_deployment_name_fits_the_common_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """The longest accepted deployment name still gives a CN of at most 64 characters."""
    with pytest.raises(ValidationError, match="at most 55"):
        Config(domain="example.org", deployment="x" * 56)
    _deployment(monkeypatch, "x" * 55)
    assert len(certificate_identity(make_user())[0]) == 64


def test_wants_certificate() -> None:
    now = datetime.now(UTC)
    assert wants_certificate(make_user(approved_at=now))
    assert not wants_certificate(make_user())
    assert not wants_certificate(make_user(approved_at=now, revoked_at=now))
    assert not wants_certificate(make_user(certificate_approved_at=now))


CN = "local-dev#0123abcd"
URI = "urn:uuid:9a1f0c6e-6f3e-4c55-8a3b-3c8f8b7f0d21"


def _csr(
    key: ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey | None = None,
    common_name: str = CN,
    sans: list[x509.GeneralName] | None = None,
    extra: x509.ExtensionType | None = None,
) -> bytes:
    """PEM CSR as a browser would build it, with overridable parts."""
    builder = x509.CertificateSigningRequestBuilder().subject_name(
        x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    )
    builder = builder.add_extension(
        x509.SubjectAlternativeName(sans if sans is not None else [x509.UniformResourceIdentifier(URI)]),
        critical=False,
    )
    if extra is not None:
        builder = builder.add_extension(extra, critical=False)
    signed = builder.sign(key or ec.generate_private_key(ec.SECP256R1()), hashes.SHA256())
    return signed.public_bytes(serialization.Encoding.PEM)


def test_check_csr_accepts_exact_identity() -> None:
    csr = check_csr(_csr(), CN, URI)
    assert isinstance(csr.public_key(), ec.EllipticCurvePublicKey)


def _bad_signature() -> bytes:
    der = bytearray(x509.load_pem_x509_csr(_csr()).public_bytes(serialization.Encoding.DER))
    der[-1] ^= 1
    return x509.load_der_x509_csr(bytes(der)).public_bytes(serialization.Encoding.PEM)


@pytest.mark.parametrize(
    ("pem", "message"),
    [
        (b"not a csr", "not a valid PEM"),
        (lambda: _csr(key=rsa.generate_private_key(public_exponent=65537, key_size=2048)), "P-256"),
        (lambda: _csr(key=ec.generate_private_key(ec.SECP384R1())), "P-256"),
        (_bad_signature, "signature"),
        (lambda: _csr(common_name="alpha"), "subject"),
        (lambda: _csr(sans=[x509.UniformResourceIdentifier("urn:uuid:other")]), "subjectAltName"),
        (
            lambda: _csr(sans=[x509.UniformResourceIdentifier(URI), x509.DNSName("example.org")]),
            "subjectAltName",
        ),
        (lambda: _csr(extra=x509.BasicConstraints(ca=True, path_length=None)), "subjectAltName"),
    ],
    ids=["garbage", "rsa", "p384", "bad-signature", "wrong-cn", "wrong-uri", "extra-san", "extra-extension"],
)
def test_check_csr_rejects(pem: bytes | Callable[[], bytes], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_csr(pem if isinstance(pem, bytes) else pem(), CN, URI)


async def test_one_shot_issuance_and_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Publish exact cert metadata, preserve other annotations, and never rotate on rename/config."""
    user = make_user(approved_at=datetime.now(UTC))
    assert user.metadata is not None
    user.metadata.annotations = {"example.org/keep": "yes"}
    ctx = _context(user)
    await _reconcile(ctx)
    assert ctx.conditions[-1] == (CERTIFICATE_READY_CONDITION, False, "Issuing", "")
    assert not any(isinstance(item, Certificate) for item in ctx.ensured)
    request = await _issued(ctx)
    await _reconcile(ctx)
    current = await _current(ctx)
    assert current.metadata is not None
    annotations = current.metadata.annotations or {}
    assert annotations["example.org/keep"] == "yes"
    record = json.loads(annotations[ACCEPTED_CREDENTIALS_ANNOTATION])
    assert record["version"] == 1 and len(record["accepted"]) == 1
    assert request.status is not None and request.status.certificate is not None
    leaf = x509.load_pem_x509_certificates(base64.b64decode(request.status.certificate))[0]
    credential = record["accepted"][0]
    assert credential["fingerprintSha256"] == leaf.fingerprint(hashes.SHA256()).hex()
    assert credential["serial"] == format(leaf.serial_number, "x")
    assert credential["issuerId"].startswith("sha256:")
    secret = await ctx.get(Secret, user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    assert ctx.status["public_key"] == public_key_fingerprint(secret)
    assert ctx.status["public_key"] != credential["fingerprintSha256"]
    assert secret.type == "kubernetes.io/tls" and secret.data is not None and "ca.crt" in secret.data
    assert ctx.conditions[-1] == (CERTIFICATE_READY_CONDITION, True, "Issued", "")
    current.spec.callsign = "renamed"
    _deployment(monkeypatch, "another-deployment")
    monkeypatch.setenv("USER_CERTIFICATE_DURATION", "24h")
    patches = len(ctx.clients[User].patches)
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert len(ctx.clients[User].patches) == patches
    assert not any(isinstance(item, CertificateRequest) for item in ctx.ensured)
    assert (await ctx.get(Secret, secret.name or "", namespace=PUBLIC_CERT_NAMESPACE)).data == secret.data


@pytest.mark.parametrize("missing", [Secret, CertificateRequest])
async def test_missing_material_requires_fresh_approval(missing: type[Secret] | type[CertificateRequest]) -> None:
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    await _issued(ctx)
    await _reconcile(ctx)
    user = await _current(ctx)
    client = await ctx.client(missing)
    await client.delete(user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert ctx.ensured == []
    assert ctx.status["public_key"] is None
    assert ctx.conditions[-1][2] == "FreshApprovalRequired"
    current = await _current(ctx)
    assert current.metadata is not None
    assert (current.metadata.annotations or {})[ACCEPTED_CREDENTIALS_ANNOTATION] == EMPTY_CREDENTIALS
    assert current.spec.approved_at is not None
    current.spec.certificate_approved_at = current.spec.approved_at + timedelta(seconds=1)
    await _reconcile(ctx)
    assert any(isinstance(item, CertificateRequest) for item in ctx.ensured)
    assert (await _current(ctx)).spec.approved_at == user.spec.approved_at


async def test_expiry_does_not_renew() -> None:
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    await _issued(ctx, expired=True)
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert ctx.ensured == []
    assert ctx.status["public_key"] is None
    assert ctx.conditions[-1][2] == "CertificateOutsideValidity"


async def test_same_key_different_certificates_have_distinct_accepted_fingerprints() -> None:
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    user = await _current(ctx)
    secret = await ctx.get(Secret, user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    first = accepted_credential(user, await _issued(ctx), secret)
    second = accepted_credential(user, await _issued(ctx), secret)
    assert first["fingerprintSha256"] != second["fingerprintSha256"]
    assert first["issuerId"] != second["issuerId"]


@pytest.mark.parametrize("tamper", ["identity", "key", "ca", "owner"])
async def test_invalid_issuance_is_not_accepted(tamper: str) -> None:
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    request = await _issued(ctx)
    user = await _current(ctx)
    secret = await ctx.get(Secret, user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    if tamper == "identity":
        assert user.metadata is not None
        user.metadata.uid = "00000000-0000-0000-0000-000000000001"
    elif tamper == "key":
        secret.data = new_request(user)[0].data
    elif tamper == "ca":
        assert request.status is not None
        request.status.ca = None
    else:
        assert secret.metadata is not None
        secret.metadata.owner_references = []
    with pytest.raises(ValueError):
        await _reconcile(ctx)
    assert user.metadata is not None
    assert not json.loads((user.metadata.annotations or {}).get(ACCEPTED_CREDENTIALS_ANNOTATION, EMPTY_CREDENTIALS))[
        "accepted"
    ]


@pytest.mark.parametrize("revoke", [False, True])
async def test_cleanup_precedes_missing_references(revoke: bool) -> None:
    user = make_user(approved_at=datetime.now(UTC))
    ctx = _context(user)
    await _reconcile(ctx)
    await _issued(ctx)
    await _reconcile(ctx)
    current = await _current(ctx)
    current.spec.role_refs = make_user(roles=["missing"]).spec.role_refs
    if revoke:
        current.spec.revoked_at = datetime.now(UTC)
    else:
        current.spec.approved_at = None
    with pytest.raises(Wait):
        await reconcile_user(current, cast(Context[User], ctx))
    assert ctx.clients[Secret].deleted[-1] == (PUBLIC_CERT_NAMESPACE, user_secret_name(user))
    assert ctx.clients[CertificateRequest].deleted[-1] == (PUBLIC_CERT_NAMESPACE, user_certificate_name(user))
    assert ctx.status["public_key"] is None
    current = await _current(ctx)
    assert current.metadata is not None
    assert (current.metadata.annotations or {})[ACCEPTED_CREDENTIALS_ANNOTATION] == EMPTY_CREDENTIALS
    assert APPROVAL_ANNOTATION in (current.metadata.annotations or {})
    await finalize_user(current, cast(Context[User], ctx))


async def test_reusing_consumed_approval_does_not_issue_again() -> None:
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    user = await _current(ctx)
    user.spec.revoked_at = datetime.now(UTC)
    await _reconcile(ctx)
    user = await _current(ctx)
    user.spec.revoked_at = None
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert ctx.ensured == []
    assert ctx.conditions[-1][2] == "FreshApprovalRequired"


async def test_stale_approval_cannot_create_resources() -> None:
    user = make_user(approved_at=datetime.now(UTC))
    ctx = _context(user)
    stale = user.model_copy(deep=True)
    assert user.metadata is not None
    user.metadata.resource_version = "2"
    user.spec.revoked_at = datetime.now(UTC)
    with pytest.raises(ResourceConflict):
        await reconcile_certificate(stale, cast(Context[User], ctx))
    assert ctx.ensured == []


async def test_legacy_certificate_is_removed_without_replacement() -> None:
    user = make_user(approved_at=datetime.now(UTC))
    ctx = _context(user)
    legacy = Certificate(
        metadata=ObjectMeta(name=user_certificate_name(user), namespace=PUBLIC_CERT_NAMESPACE, uid="old")
    )
    assert legacy.metadata is not None and user.metadata is not None and user.metadata.uid is not None
    legacy.metadata.owner_references = [
        OwnerReference(
            api_version=user.gvk().api_version,
            kind="User",
            name=user.name or "",
            uid=user.metadata.uid,
            controller=True,
        )
    ]
    ctx.clients[Certificate] = FakeClient([legacy])
    await _reconcile(ctx)
    assert ctx.clients[Certificate].deleted == [(PUBLIC_CERT_NAMESPACE, user_certificate_name(user))]
    assert ctx.ensured == []
    assert ctx.conditions[-1][2] == "FreshApprovalRequired"
    await _reconcile(ctx)
    assert ctx.ensured == []


def test_public_key_fingerprint_requires_certificate() -> None:
    with pytest.raises(ValueError, match=r"tls\.crt"):
        public_key_fingerprint(Secret())


async def test_old_material_cannot_be_accepted_under_a_new_approval() -> None:
    """A failed replacement cannot publish the previous request as the newly approved credential."""
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    await _reconcile(ctx)
    await _issued(ctx)
    user = await _current(ctx)
    assert user.spec.approved_at is not None and user.metadata is not None
    user.spec.certificate_approved_at = user.spec.approved_at + timedelta(seconds=1)
    user.metadata.annotations = {APPROVAL_ANNOTATION: user.spec.certificate_approved_at.isoformat()}
    with pytest.raises(ValueError, match="another approval"):
        await _reconcile(ctx)
    assert ctx.status["public_key"] is None


async def test_partial_creation_does_not_retry_issuance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Approval stays consumed if creation fails after reservation."""
    ctx = _context(make_user(approved_at=datetime.now(UTC)))
    original = ctx.ensure

    async def fail_request(resource: Secret | CertificateRequest) -> Secret | CertificateRequest:
        if isinstance(resource, CertificateRequest):
            raise RuntimeError("creation interrupted")
        return await original(resource)

    monkeypatch.setattr(ctx, "ensure", fail_request)
    with pytest.raises(RuntimeError, match="interrupted"):
        await _reconcile(ctx)
    monkeypatch.setattr(ctx, "ensure", original)
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert ctx.ensured == []
    assert ctx.conditions[-1][2] == "FreshApprovalRequired"


@pytest.mark.parametrize("explicit_initial", [False, True])
async def test_rotation_preserves_original_approval(explicit_initial: bool) -> None:
    """A fresh certificate approval changes the key once and preserves enrollment history."""
    original = datetime.now(UTC)
    first_approval = original + timedelta(seconds=1) if explicit_initial else original
    ctx = _context(
        make_user(
            approved_at=original,
            certificate_approved_at=first_approval if explicit_initial else None,
        )
    )
    await _reconcile(ctx)
    await _issued(ctx)
    await _reconcile(ctx)
    user = await _current(ctx)
    old_secret = await ctx.get(Secret, user_secret_name(user), namespace=PUBLIC_CERT_NAMESPACE)
    user.spec.certificate_approved_at = first_approval + timedelta(seconds=1)
    await _reconcile(ctx)
    await _issued(ctx)
    await _reconcile(ctx)
    current = await _current(ctx)
    assert current.spec.approved_at == original
    assert current.metadata is not None
    assert (current.metadata.annotations or {})[APPROVAL_ANNOTATION] == user.spec.certificate_approved_at.isoformat()
    new_secret = await ctx.get(Secret, user_secret_name(current), namespace=PUBLIC_CERT_NAMESPACE)
    assert new_secret.data is not None and old_secret.data is not None
    assert new_secret.data["tls.key"] != old_secret.data["tls.key"]
    assert new_secret.data["tls.crt"] != old_secret.data["tls.crt"]
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert not any(isinstance(item, CertificateRequest) for item in ctx.ensured)


@pytest.mark.parametrize("change", ["enrollment", "clear", "older", "same"])
async def test_only_fresh_certificate_approval_can_replace(change: str) -> None:
    """Enrollment edits and old certificate approvals preserve the current certificate."""
    original = datetime.now(UTC)
    approved = original + timedelta(seconds=1)
    ctx = _context(make_user(approved_at=original, certificate_approved_at=approved))
    await _reconcile(ctx)
    await _issued(ctx)
    await _reconcile(ctx)
    current = await _current(ctx)
    if change == "enrollment":
        current.spec.approved_at = approved + timedelta(seconds=1)
    elif change == "clear":
        current.spec.certificate_approved_at = None
    elif change == "older":
        current.spec.certificate_approved_at = original
    ctx.ensured.clear()
    fingerprint = ctx.status["public_key"]
    await _reconcile(ctx)
    assert not any(isinstance(item, CertificateRequest) for item in ctx.ensured)
    assert ctx.status["public_key"] == fingerprint
    assert ctx.conditions[-1][2] == "Issued"
    await ctx.clients[Secret].delete(user_secret_name(current), namespace=PUBLIC_CERT_NAMESPACE)
    ctx.ensured.clear()
    await _reconcile(ctx)
    assert ctx.ensured == []
    assert ctx.conditions[-1][2] == "FreshApprovalRequired"
