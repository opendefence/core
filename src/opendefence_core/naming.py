"""Names shared by the operator, the REST API, and the package manifests.

YAML under manifests/ and the Tiltfile can't import these; keep them in sync.
"""

from lib_opendefence_core.models.v1alpha1 import User

SYSTEM_NAMESPACE = "opendefence-system"
"""Namespace of the operator and the REST API."""

PUBLIC_CERT_NAMESPACE = "opendefence-public-certs"
"""Namespace of the users' certificate signing requests."""

PUBLIC_ISSUER = "public-issuer"
"""Base's ClusterIssuer for public certificates, including the users' mTLS certificates."""

OPERATOR_NAME = "core-operator"
"""Operator Application name: its Deployment, ServiceAccount, Service, Lease, and RBAC."""

OPERATOR_TLS_SECRET = "core-operator-tls"  # nosec B105  # pragma: allowlist secret
"""Serving certificate of the operator's admission webhook."""

SUPERADMIN_ROLE = "superadmin"
"""Role that grants full administration of the platform."""


def user_certificate_name(user: User) -> str:
    """Name of the user's one-shot cert-manager CertificateRequest in PUBLIC_CERT_NAMESPACE."""
    return f"user-{user.name}"
