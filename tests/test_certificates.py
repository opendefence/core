"""User mTLS certificate helpers, reconcile branches, and cleanup."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateStatus, ConditionModel
from cloudcoil.models.kubernetes.core.v1 import Secret
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from opendefence_core.k8s_operator.controllers._certificates import (
    ISSUED_REASON,
    ISSUING_REASON,
    PENDING_REASON,
    REVOKED_REASON,
    desired_certificate,
    public_key_fingerprint,
    reconcile_certificate,
    wants_certificate,
)
from opendefence_core.k8s_operator.controllers.users import finalize_user
from lib_opendefence_core.models.v1alpha1 import CERTIFICATE_READY_CONDITION, User
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, PUBLIC_ISSUER, user_certificate_name, user_secret_name
from tests.factories import make_user
from tests.fakes import FakeClient, FakeContext

CALLSIGN = "testuser"
NAME = "user-testuser"


def _cert(
    subject: str, key: ec.EllipticCurvePrivateKey, issuer: str, signer: ec.EllipticCurvePrivateKey
) -> x509.Certificate:
    now = datetime.now(UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer)]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(signer, hashes.SHA256())
    )


def _spki_sha256(key: ec.EllipticCurvePrivateKey) -> str:
    spki = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).hexdigest()


def _observed_certificate(user: User, *, ready: bool) -> Certificate:
    """The desired Certificate as cert-manager would report it back."""
    certificate = desired_certificate(user)
    assert certificate.metadata is not None
    certificate.metadata.generation = 1
    certificate.status = CertificateStatus(
        conditions=[ConditionModel(type="Ready", status="True" if ready else "False", observed_generation=1)]
    )
    return certificate


def _tls_secret(leaf_key: ec.EllipticCurvePrivateKey) -> Secret:
    ca_key = ec.generate_private_key(ec.SECP256R1())
    leaf = _cert(CALLSIGN, leaf_key, "test-ca", ca_key)
    return Secret(
        metadata=ObjectMeta(name=NAME, namespace=PUBLIC_CERT_NAMESPACE),
        data={"tls.crt": base64.b64encode(leaf.public_bytes(serialization.Encoding.PEM)).decode()},
    )


def test_names() -> None:
    """The Certificate and its Secret are named after the user."""
    user = make_user(CALLSIGN)
    assert user_certificate_name(user) == NAME
    assert user_secret_name(user) == NAME


def test_wants_certificate() -> None:
    """Approved and not revoked -> True; unapproved or revoked -> False."""
    now = datetime.now(UTC)
    assert wants_certificate(make_user(CALLSIGN, approved_at=now))
    assert not wants_certificate(make_user(CALLSIGN))
    assert not wants_certificate(make_user(CALLSIGN, approved_at=now, revoked_at=now))


def test_desired_certificate() -> None:
    """Name, namespace, CN=callsign, ECDSA P-256, rotationPolicy Never, usages, issuerRef."""
    user = make_user(CALLSIGN, approved_at=datetime.now(UTC))
    certificate = desired_certificate(user)
    assert certificate.metadata is not None
    assert certificate.metadata.name == NAME
    assert certificate.metadata.namespace == PUBLIC_CERT_NAMESPACE
    spec = certificate.spec
    assert spec is not None
    assert spec.secret_name == NAME
    assert spec.common_name == CALLSIGN
    assert spec.private_key is not None
    assert spec.private_key.algorithm == "ECDSA"
    assert spec.private_key.size == 256
    assert spec.private_key.rotation_policy == "Never"
    assert spec.usages == ["digital signature", "content commitment", "key encipherment", "client auth"]
    assert spec.issuer_ref.name == PUBLIC_ISSUER
    assert spec.issuer_ref.kind == "ClusterIssuer"
    assert spec.issuer_ref.group == "cert-manager.io"


def test_public_key_fingerprint_parses_leaf() -> None:
    """Fingerprint comes from the leaf of a chain generated with cryptography."""
    ca_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    ca = _cert("test-ca", ca_key, "test-ca", ca_key)
    leaf = _cert(CALLSIGN, leaf_key, "test-ca", ca_key)
    chain = leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    secret = Secret(
        metadata=ObjectMeta(name=NAME, namespace=PUBLIC_CERT_NAMESPACE),
        data={"tls.crt": base64.b64encode(chain).decode()},
    )

    fingerprint = public_key_fingerprint(secret)

    assert fingerprint == _spki_sha256(leaf_key)
    assert fingerprint != _spki_sha256(ca_key)


def test_public_key_fingerprint_requires_tls_crt() -> None:
    """A Secret without tls.crt raises ValueError."""
    secret = Secret(metadata=ObjectMeta(name=NAME, namespace=PUBLIC_CERT_NAMESPACE), data={})
    with pytest.raises(ValueError, match=r"tls\.crt"):
        public_key_fingerprint(secret)


async def test_reconcile_certificate_waits_until_ready() -> None:
    """Not Ready -> CertificateReady=False reason Issuing, no publicKey."""
    user = make_user(CALLSIGN, approved_at=datetime.now(UTC))
    ctx = FakeContext(clients={Certificate: FakeClient([_observed_certificate(user, ready=False)])})

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert [item.name for item in ctx.ensured] == [NAME]
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, ISSUING_REASON, "")]
    assert "public_key" not in ctx.status


async def test_reconcile_certificate_records_ready_certificate() -> None:
    """Ready -> reads the Secret and writes publicKey, CertificateReady=True."""
    user = make_user(CALLSIGN, approved_at=datetime.now(UTC))
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    ctx = FakeContext(
        clients={
            Certificate: FakeClient([_observed_certificate(user, ready=True)]),
            Secret: FakeClient([_tls_secret(leaf_key)]),
        }
    )

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert ctx.status["public_key"] == _spki_sha256(leaf_key)
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, True, ISSUED_REASON, "")]


@pytest.mark.parametrize(
    ("approved", "revoked", "reason"),
    [(False, False, PENDING_REASON), (True, True, REVOKED_REASON)],
    ids=["unapproved", "revoked"],
)
async def test_reconcile_certificate_removes_certificate_and_key(approved: bool, revoked: bool, reason: str) -> None:
    """Revoked or unapproved -> deletes the Certificate and its key pair Secret, clears publicKey.

    A leftover Secret would hand its key to the next Certificate (rotationPolicy Never).
    """
    now = datetime.now(UTC)
    user = make_user(CALLSIGN, approved_at=now if approved else None, revoked_at=now if revoked else None)
    certificates = FakeClient([_observed_certificate(user, ready=True)])
    secrets = FakeClient([_tls_secret(ec.generate_private_key(ec.SECP256R1()))])
    ctx = FakeContext(clients={Certificate: certificates, Secret: secrets})

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert certificates.deleted == [(PUBLIC_CERT_NAMESPACE, NAME)]
    assert secrets.deleted == [(PUBLIC_CERT_NAMESPACE, NAME)]
    assert ctx.ensured == []
    assert ctx.status == {"public_key": None}
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, reason, "")]


async def test_reconcile_certificate_tolerates_missing_certificate_and_key() -> None:
    """Deleting an already-absent Certificate and Secret is not an error."""
    ctx = FakeContext()

    await reconcile_certificate(make_user(CALLSIGN), cast(Context[User], ctx))

    assert ctx.status == {"public_key": None}
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, PENDING_REASON, "")]


async def test_finalizer_removes_certificate_and_key() -> None:
    """Deleting a User removes its key pair Secret, which garbage collection would leave behind."""
    user = make_user(CALLSIGN, approved_at=datetime.now(UTC))
    certificates = FakeClient([_observed_certificate(user, ready=True)])
    secrets = FakeClient([_tls_secret(ec.generate_private_key(ec.SECP256R1()))])
    ctx = FakeContext(clients={Certificate: certificates, Secret: secrets})

    await finalize_user(user, cast(Context[User], ctx))

    assert certificates.deleted == [(PUBLIC_CERT_NAMESPACE, NAME)]
    assert secrets.deleted == [(PUBLIC_CERT_NAMESPACE, NAME)]
