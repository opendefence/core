"""Client certificates that Traefik verified and forwarded to the API."""

import base64
from contextlib import suppress
from datetime import UTC, datetime
from urllib.parse import unquote
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from lib_opendefence_core.models.v1alpha1 import User
from opendefence_core.api.lib.uids import by_uid
from opendefence_core.certificates import accepted_entry

CLIENT_CERT_HEADER = "X-Forwarded-Tls-Client-Cert"
"""Set by Traefik passTLSClientCert; strip-identity-headers removes any value the client sends."""


def leaf_certificate(value: str) -> x509.Certificate:
    """First certificate of a passTLSClientCert header: URL-escaped, comma-separated base64 DER."""
    return x509.load_der_x509_certificate(base64.b64decode(unquote(value).split(",", 1)[0], validate=True))


def _uid(leaf: x509.Certificate) -> str | None:
    """User UID from the `urn:uuid:<uid>` SAN; the CN is only a display label."""
    try:
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound, x509.DuplicateExtension, ValueError:
        return None
    for uri in san.get_values_for_type(x509.UniformResourceIdentifier):
        if uri.startswith("urn:uuid:"):
            with suppress(ValueError):
                return str(UUID(uri.removeprefix("urn:uuid:")))
    return None


async def certificate_user(leaf: x509.Certificate) -> User | None:
    """The User this exact certificate is accepted for now, or None.

    The fingerprint ties the request to the certificate the operator verified,
    so a certificate that only copies the uid and serial is rejected.
    """
    uid = _uid(leaf)
    user = await by_uid(User, uid) if uid else None
    if user is None:
        return None
    entry = accepted_entry(user, leaf.serial_number, datetime.now(UTC))
    if entry is None or entry["fingerprintSha256"] != leaf.fingerprint(hashes.SHA256()).hex():
        return None
    return user
