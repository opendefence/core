"""Names shared by the operator, the REST API, and the package manifests.

YAML under manifests/ and the Tiltfile can't import these; keep them in sync.
"""

from lib_opendefence_core.models.v1alpha1 import User

SYSTEM_NAMESPACE = "opendefence-system"
"""Namespace of the operator and the REST API."""

CLIENT_CERT_NAMESPACE = "opendefence-client-certs"
"""Namespace of the users' certificate signing requests."""

CLIENT_ISSUER = "core-client-issuer"
"""ClusterIssuer for the users' mTLS certificates: base's client CA, with core's OCSP URL."""

OPERATOR_NAME = "core-operator"
"""Operator Application name: its Deployment, ServiceAccount, Service, Lease, and RBAC."""

OPERATOR_TLS_SECRET = "core-operator-tls"  # nosec B105  # pragma: allowlist secret
"""Serving certificate of the operator's admission webhook."""

SUPERADMIN_ROLE = "superadmin"
"""Role that grants full administration of the platform."""

TRAEFIK_NAMESPACE = "traefik-system"
"""Namespace of Traefik and of the middlewares that every route uses."""

STRIP_IDENTITY_HEADERS_MIDDLEWARE = "strip-identity-headers"
"""Middleware that clears the identity headers a client sends."""

HSTS_MIDDLEWARE = "hsts"
"""Middleware that sets the Strict-Transport-Security header."""


def user_certificate_name(user: User) -> str:
    """Name of the user's one-shot cert-manager CertificateRequest in CLIENT_CERT_NAMESPACE."""
    return f"user-{user.name}"
