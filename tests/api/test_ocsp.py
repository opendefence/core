"""OCSP answers from the Users' accepted credentials, signed by a delegated responder."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509 import ocsp
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.config import get_api_config
from opendefence_core.api.routes.certificates.ocsp.responder import EXTENDED_REVOKE, build_ocsp_response
from opendefence_core.api.routes.certificates.ocsp.status import NOT_ISSUED_TIME
from opendefence_core.certificates import certificate_identity
from tests.factories import accept_certificate, make_client_certificate, make_user

Signer = tuple[x509.Certificate, x509.Certificate]
"""The mounted client CA and the responder certificate it issued."""


def _issue(subject: str, key: ec.EllipticCurvePrivateKey, issuer: x509.Name) -> x509.CertificateBuilder:
    start = datetime.now(UTC) - timedelta(hours=1)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)]))
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(start + timedelta(days=1))
    )


@pytest.fixture
def signer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Signer:
    """A client CA and its delegated responder, mounted as the cert-manager Secret would be."""
    ca_key, responder_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "client CA")])
    ca = (
        _issue("client CA", ca_key, ca_name)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    responder = (
        _issue("responder", responder_key, ca_name)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.OCSP_SIGNING]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    (tmp_path / "ca.crt").write_bytes(ca.public_bytes(pem))
    (tmp_path / "tls.crt").write_bytes(responder.public_bytes(pem))
    (tmp_path / "tls.key").write_bytes(
        responder_key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    monkeypatch.setattr(get_api_config(), "ocsp_signer_path", tmp_path)
    return ca, responder


def _request(
    certificate: x509.Certificate, issuer: x509.Certificate, algorithm: hashes.HashAlgorithm, nonce: bytes = b""
) -> bytes:
    builder = ocsp.OCSPRequestBuilder().add_certificate(certificate, issuer, algorithm)
    if nonce:
        builder = builder.add_extension(x509.OCSPNonce(nonce), critical=False)
    return builder.build().public_bytes(serialization.Encoding.DER)


async def _answer(der: bytes) -> ocsp.OCSPResponse:
    return ocsp.load_der_ocsp_response((await build_ocsp_response(der))[0])


def _accepted_user(users: list[User], ca: x509.Certificate, revoked_at: datetime | None = None) -> x509.Certificate:
    """A listed user with an accepted certificate from the CA."""
    user = make_user(revoked_at=revoked_at)
    certificate = make_client_certificate(*certificate_identity(user), issuer=ca.subject)
    accept_certificate(user, certificate)
    users.append(user)
    return certificate


@pytest.mark.parametrize("algorithm", [hashes.SHA1(), hashes.SHA256()])
async def test_accepted_certificate_is_good(users: list[User], signer: Signer, algorithm: hashes.HashAlgorithm) -> None:
    """An accepted serial is good, in a response the bundled responder certificate signed."""
    ca, responder = signer
    response = await _answer(_request(_accepted_user(users, ca), ca, algorithm))
    assert response.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL
    assert response.certificate_status == ocsp.OCSPCertStatus.GOOD
    assert response.certificates == [responder]
    assert response.responder_key_hash == x509.SubjectKeyIdentifier.from_public_key(responder.public_key()).digest
    public_key = responder.public_key()
    assert isinstance(public_key, ec.EllipticCurvePublicKey) and response.signature_hash_algorithm is not None
    public_key.verify(response.signature, response.tbs_response_bytes, ec.ECDSA(response.signature_hash_algorithm))


async def test_responder_certificate_is_good(users: list[User], signer: Signer) -> None:
    """Clients that check the responder certificate itself get good."""
    ca, responder = signer
    response = await _answer(_request(responder, ca, hashes.SHA256()))
    assert response.certificate_status == ocsp.OCSPCertStatus.GOOD


@pytest.mark.parametrize("revoked", [False, True])
async def test_other_serials_are_revoked_as_not_issued(users: list[User], signer: Signer, revoked: bool) -> None:
    """Unknown serials and revoked users' certificates get the RFC 6960 non-issued answer, never unknown."""
    ca, _ = signer
    if revoked:
        certificate = _accepted_user(users, ca, datetime.now(UTC))
    else:
        certificate = make_client_certificate("unknown", "urn:uuid:unknown", serial=0xBAD, issuer=ca.subject)
    response = await _answer(_request(certificate, ca, hashes.SHA256()))
    assert response.certificate_status == ocsp.OCSPCertStatus.REVOKED
    assert response.revocation_time_utc == NOT_ISSUED_TIME
    assert response.revocation_reason == x509.ReasonFlags.certificate_hold
    assert response.extensions.get_extension_for_oid(EXTENDED_REVOKE.oid).value == EXTENDED_REVOKE


async def test_nonce(users: list[User], signer: Signer) -> None:
    """The nonce is echoed; one over 32 bytes is malformed."""
    ca, _ = signer
    certificate = _accepted_user(users, ca)
    der, meta = await build_ocsp_response(_request(certificate, ca, hashes.SHA256(), b"n" * 32))
    assert meta.nonce
    assert ocsp.load_der_ocsp_response(der).extensions.get_extension_for_class(x509.OCSPNonce).value.nonce == b"n" * 32
    response = await _answer(_request(certificate, ca, hashes.SHA256(), b"n" * 33))
    assert response.response_status == ocsp.OCSPResponseStatus.MALFORMED_REQUEST


async def test_refusals(signer: Signer) -> None:
    """Garbage is malformed, and a request for another CA is unauthorized."""
    assert (await _answer(b"garbage")).response_status == ocsp.OCSPResponseStatus.MALFORMED_REQUEST
    other_ca = make_client_certificate("other", "urn:uuid:other")
    response = await _answer(_request(other_ca, other_ca, hashes.SHA256()))
    assert response.response_status == ocsp.OCSPResponseStatus.UNAUTHORIZED


async def test_failures_are_internal_errors(
    users: list[User], signer: Signer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed User list or a missing responder mount answers internalError, which clients must deny."""
    ca, _ = signer
    request = _request(_accepted_user(users, ca), ca, hashes.SHA256())

    async def unavailable(cls: type[User], **kwargs: object) -> None:
        _ = cls, kwargs
        raise ConnectionError("API server unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(User, "async_list", classmethod(unavailable))
        assert (await _answer(request)).response_status == ocsp.OCSPResponseStatus.INTERNAL_ERROR
    monkeypatch.setattr(get_api_config(), "ocsp_signer_path", tmp_path / "missing")
    assert (await _answer(request)).response_status == ocsp.OCSPResponseStatus.INTERNAL_ERROR
