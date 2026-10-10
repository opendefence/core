from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric import rsa, ec


def build_pfx(callsign: str, key_pem: bytes, chain_pem: bytes) -> bytes:
    """PKCS#12: legacy 3DES, password and friendly name = callsign."""
    key = serialization.load_pem_private_key(key_pem, password=None)
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise ValueError(f"Unsupported key type {type(key).__name__}")
    leaf, *chain = x509.load_pem_x509_certificates(chain_pem)
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())  # nosec B303 - legacy format for device compatibility
        .build(callsign.encode())
    )
    return pkcs12.serialize_key_and_certificates(callsign.encode(), key, leaf, chain or None, encryption)
