"""User mTLS certificate helpers and reconcile branches."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import Context
from cloudcoil.models.cert_manager.v1 import Certificate, CertificateStatus, ConditionModel
from cloudcoil.models.kubernetes.core.v1 import Secret
from cloudcoil.resources import Resource
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from opendefence_core.k8s_operator.app import app
from opendefence_core.k8s_operator.controllers._certificates import (
    PUBLIC_CERT_ISSUER,
    PUBLIC_CERT_NAMESPACE,
    ISSUED_REASON,
    ISSUING_REASON,
    PENDING_REASON,
    REVOKED_REASON,
    certificate_name,
    desired_certificate,
    public_key_fingerprint,
    reconcile_certificate,
    secret_name,
    wants_certificate,
)
from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION
from opendefence_core.k8s_operator.models.v1alpha1.user import CERTIFICATE_READY_CONDITION, User, UserSpec
from opendefence_core.k8s_operator.models.v1alpha1 import (
    ObjectRef,
)
from tests.conftest import FakeClient, FakeContext

CALLSIGN = "testuser"


def _user(
    name: str,
    *,
    roles: list[str] | None = None,
    groups: list[str] | None = None,
    approved_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, uid=f"uid-{name}"),
        spec=UserSpec(
            callsign=name,
            role_refs=[ObjectRef(name=item) for item in roles or []],
            group_refs=[ObjectRef(name=item) for item in groups or []],
            approved_at=approved_at,
            revoked_at=revoked_at,
        ),
    )


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


def test_manifests_grant_certificate_and_secret_access() -> None:
    """Users controller can manage Certificates and read user cert Secrets."""
    documents = app.manifests(include_webhooks=False)
    cluster_role = next(document for document in documents if document["kind"] == "ClusterRole")
    certificate_rule = next(rule for rule in cluster_role["rules"] if rule.get("resources") == ["certificates"])
    assert "delete" in certificate_rule["verbs"]
    secret_role = next(
        document
        for document in documents
        if document["kind"] == "Role" and document["metadata"]["namespace"] == "opendefence-public-certs"
    )
    assert secret_role["rules"] == [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]}]


def test_certificate_name():
    user = _user(CALLSIGN)
    assert certificate_name(user) == "user-testuser"


def test_secret_name():
    user = _user(CALLSIGN)
    assert secret_name(user) == "user-testuser"


def test_wants_certificate() -> None:
    """Approved and not revoked -> True; unapproved or revoked -> False."""
    time_now = datetime.now()
    assert wants_certificate(_user(CALLSIGN, approved_at=time_now))
    assert not wants_certificate(_user(CALLSIGN))
    assert not wants_certificate(_user(CALLSIGN, approved_at=time_now, revoked_at=time_now))


def test_desired_certificate() -> None:
    """Name, namespace, CN=callsign, ECDSA P-256, rotationPolicy Never, usages, issuerRef."""
    user = _user(CALLSIGN, approved_at=datetime.now(UTC))
    certificate = desired_certificate(user)
    assert certificate.metadata is not None
    assert certificate.metadata.name == certificate_name(user)
    assert certificate.metadata.namespace == PUBLIC_CERT_NAMESPACE
    spec = certificate.spec
    assert spec is not None
    assert spec.secret_name == secret_name(user)
    assert spec.common_name == CALLSIGN
    assert spec.private_key is not None
    assert spec.private_key.algorithm == "ECDSA"
    assert spec.private_key.size == 256
    assert spec.private_key.rotation_policy == "Never"
    assert spec.usages == ["digital signature", "content commitment", "key encipherment", "client auth"]
    assert spec.issuer_ref.name == PUBLIC_CERT_ISSUER
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
        metadata=ObjectMeta(name="user-testuser", namespace=PUBLIC_CERT_NAMESPACE),
        data={"tls.crt": base64.b64encode(chain).decode()},
    )

    fingerprint = public_key_fingerprint(secret)

    assert fingerprint == _spki_sha256(leaf_key)
    assert fingerprint != _spki_sha256(ca_key)


def test_public_key_fingerprint_requires_tls_crt() -> None:
    """A Secret without tls.crt raises ValueError."""
    secret = Secret(metadata=ObjectMeta(name="user-testuser", namespace=PUBLIC_CERT_NAMESPACE), data={})
    with pytest.raises(ValueError, match="tls.crt"):
        public_key_fingerprint(secret)


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
        metadata=ObjectMeta(name="user-testuser", namespace=PUBLIC_CERT_NAMESPACE),
        data={"tls.crt": base64.b64encode(leaf.public_bytes(serialization.Encoding.PEM)).decode()},
    )


@pytest.mark.asyncio
async def test_reconcile_certificate_waits_until_ready() -> None:
    """Not Ready -> CertificateReady=False reason Issuing, no publicKey."""
    user = _user(CALLSIGN, approved_at=datetime.now(UTC))
    certificate = _observed_certificate(user, ready=False)
    ctx = FakeContext(clients={Certificate: FakeClient({(PUBLIC_CERT_NAMESPACE, certificate_name(user)): certificate})})

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert [item.name for item in ctx.ensured] == ["user-testuser"]
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, ISSUING_REASON, "")]
    assert "public_key" not in ctx.status


@pytest.mark.asyncio
async def test_reconcile_certificate_records_ready_certificate() -> None:
    """Ready -> reads the Secret and writes publicKey, CertificateReady=True."""
    user = _user(CALLSIGN, approved_at=datetime.now(UTC))
    certificate = _observed_certificate(user, ready=True)
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    secret = _tls_secret(leaf_key)
    ctx = FakeContext(
        clients={
            Certificate: FakeClient({(PUBLIC_CERT_NAMESPACE, certificate_name(user)): certificate}),
            Secret: FakeClient({(PUBLIC_CERT_NAMESPACE, secret_name(user)): secret}),
        }
    )

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert ctx.status["public_key"] == _spki_sha256(leaf_key)
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, True, ISSUED_REASON, "")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("approved", "revoked", "reason"),
    [(False, False, PENDING_REASON), (True, True, REVOKED_REASON)],
    ids=["unapproved", "revoked"],
)
async def test_reconcile_certificate_removes_when_not_wanted(approved: bool, revoked: bool, reason: str) -> None:
    """Revoked or unapproved -> deletes the Certificate and clears publicKey."""
    now = datetime.now(UTC)
    user = _user(CALLSIGN, approved_at=now if approved else None, revoked_at=now if revoked else None)
    certificate = _observed_certificate(user, ready=True)
    client: FakeClient[Resource] = FakeClient({(PUBLIC_CERT_NAMESPACE, certificate_name(user)): certificate})
    ctx = FakeContext(clients={Certificate: client})

    await reconcile_certificate(user, cast(Context[User], ctx))

    assert client.deleted == [(PUBLIC_CERT_NAMESPACE, "user-testuser")]
    assert ctx.ensured == []
    assert ctx.status == {"public_key": None}
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, reason, "")]


@pytest.mark.asyncio
async def test_reconcile_certificate_tolerates_missing_certificate() -> None:
    """Deleting an already-absent Certificate is not an error."""
    ctx = FakeContext()

    await reconcile_certificate(_user(CALLSIGN), cast(Context[User], ctx))

    assert ctx.status == {"public_key": None}
    assert ctx.conditions == [(CERTIFICATE_READY_CONDITION, False, PENDING_REASON, "")]
