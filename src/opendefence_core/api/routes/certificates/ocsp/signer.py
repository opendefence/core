"""OCSP response signing material.

Responses are signed by a delegated responder certificate that cert-manager
issues from client-issuer. Its Secret is mounted with tls.crt, tls.key, and
ca.crt, the client CA the responder answers for.
"""

from dataclasses import dataclass, field

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from opendefence_core.api.config import get_api_config

HASH_ALGORITHMS = {
    "sha1": hashes.SHA1,
    "sha256": hashes.SHA256,
}


@dataclass
class SignerMaterial:
    """Responder cert + key, with the CA's issuer hashes precomputed for request matching"""

    ca: x509.Certificate
    cert: x509.Certificate
    key: ec.EllipticCurvePrivateKey
    name_hashes: dict[str, bytes] = field(init=False)
    key_hashes: dict[str, bytes] = field(init=False)

    def __post_init__(self) -> None:
        # RFC 6960 4.1.1: issuerNameHash is over the DER of the issuer subject,
        # issuerKeyHash over the subjectPublicKey BIT STRING content, which for
        # EC keys is the uncompressed point.
        name_der = self.ca.subject.public_bytes()
        key_bits = self.ca.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.name_hashes = {name: _digest(name_der, alg()) for name, alg in HASH_ALGORITHMS.items()}
        self.key_hashes = {name: _digest(key_bits, alg()) for name, alg in HASH_ALGORITHMS.items()}


def _digest(data: bytes, algorithm: hashes.HashAlgorithm) -> bytes:
    """Hash data with the given algorithm"""
    hasher = hashes.Hash(algorithm)
    hasher.update(data)
    return hasher.finalize()


def get_signer() -> SignerMaterial:
    """Read the mounted material on each call, so a renewed certificate is used at once"""
    path = get_api_config().ocsp_signer_path
    key = serialization.load_pem_private_key((path / "tls.key").read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError(f"OCSP responder key is {type(key).__name__}, expected an EC key")
    return SignerMaterial(
        ca=x509.load_pem_x509_certificate((path / "ca.crt").read_bytes()),
        cert=x509.load_pem_x509_certificate((path / "tls.crt").read_bytes()),
        key=key,
    )
