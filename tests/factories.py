"""Builders for platform resources in tests."""

import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_DNS, uuid5

from cloudcoil.apimachinery import ObjectMeta, OwnerReference
from cloudcoil.models.kubernetes.core.v1 import Service
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lib_opendefence_core.models.v1alpha1 import (
    ACCEPTED_CREDENTIALS_ANNOTATION,
    API_VERSION,
    REFERENCES_RESOLVED_CONDITION,
    SYNCED_CONDITION,
    Group,
    GroupSpec,
    Integration,
    IntegrationRole,
    IntegrationSpec,
    IntegrationStatus,
    Invite,
    InviteSpec,
    InviteStatus,
    ObjectRef,
    ResolvedRef,
    Role,
    RoleSpec,
    User,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
    UserSpec,
    UserStatus,
)
from lib_opendefence_core.models.v1alpha1.common import PlatformCondition


def uid(name: str) -> str:
    """Deterministic uid for the named object, as the API server would assign one."""
    return str(uuid5(NAMESPACE_DNS, name))


def refs(names: Iterable[str]) -> list[ObjectRef]:
    """Name refs to the given objects."""
    return [ObjectRef(name=name) for name in names]


def condition(condition_type: str, status: bool, reason: str) -> PlatformCondition:
    """A condition as a controller would report it."""
    return PlatformCondition(
        last_transition_time="2026-09-13T00:00:00Z",
        message="",
        reason=reason,
        status="True" if status else "False",
        type=condition_type,
        observed_generation=1,
    )


def make_user(
    name: str = "alpha1",
    *,
    callsign: str = "foxtrot6",
    namespace: str | None = None,
    roles: Iterable[str] = (),
    groups: Iterable[str] = (),
    effective_roles: Iterable[str] = (),
    effective_groups: Iterable[str] = (),
    approval_code: str | None = None,
    approved_at: datetime | None = None,
    certificate_approved_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> User:
    """User with a stable UUID and resource version.

    The callsign is independent of the name; pass it when it matters.
    The effective roles and groups go in the status, as the operator writes them.
    """
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=uid(name), resource_version="1"),
        spec=UserSpec(
            callsign=callsign,
            role_refs=refs(roles),
            group_refs=refs(groups),
            approval_code=approval_code,
            approved_at=approved_at,
            certificate_approved_at=certificate_approved_at,
            revoked_at=revoked_at,
        ),
        status=UserStatus(
            roles=[ResolvedRef(name=role, uid=uid(role)) for role in effective_roles],
            groups=[ResolvedRef(name=group, uid=uid(group)) for group in effective_groups],
        ),
    )


def make_client_certificate(
    common_name: str, uri: str, *, serial: int = 0x1234, issuer: x509.Name | None = None
) -> x509.Certificate:
    """Client certificate whose only SAN is the URI, valid from an hour ago for a day.

    It is signed with its own key; issuer only sets the issuer name.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    start = datetime.now(UTC) - timedelta(hours=1)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer or name)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(start)
        .not_valid_after(start + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri)]), critical=False)
        .sign(key, hashes.SHA256())
    )


def accept_certificate(user: User, certificate: x509.Certificate) -> None:
    """Publish the certificate as the user's accepted credential, as the operator does."""
    assert user.metadata is not None
    entry = {
        "fingerprintSha256": certificate.fingerprint(hashes.SHA256()).hex(),
        "serial": format(certificate.serial_number, "x"),
        "notBefore": certificate.not_valid_before_utc.isoformat(),
        "notAfter": certificate.not_valid_after_utc.isoformat(),
    }
    user.metadata.annotations = {ACCEPTED_CREDENTIALS_ANNOTATION: json.dumps({"version": 1, "accepted": [entry]})}


def make_role(name: str, *, owner: str | None = None) -> Role:
    """Role displayed by its name. owner names the controlling Integration."""
    metadata = ObjectMeta(name=name, uid=uid(name))
    if owner is not None:
        metadata.owner_references = [
            OwnerReference(
                api_version=API_VERSION,
                kind="Integration",
                name=owner,
                uid=uid(owner),
                controller=True,
            )
        ]
    return Role(
        api_version=API_VERSION,
        kind="Role",
        metadata=metadata,
        spec=RoleSpec(display_name=name),
    )


def make_integration(name: str, *, roles: Iterable[str] = (), resolved: bool | None = None) -> Integration:
    """Integration displayed by its name, with a ReferencesResolved condition unless resolved is None."""
    status = (
        None
        if resolved is None
        else IntegrationStatus(conditions=[_resolved_condition(resolved)], observed_generation=1)
    )
    return Integration(
        api_version=API_VERSION,
        kind="Integration",
        metadata=ObjectMeta(name=name, uid=uid(name), generation=1),
        spec=IntegrationSpec(
            display_name=name,
            version="1.0.0",
            extra_roles=[IntegrationRole(name=role, display_name=role) for role in roles],
        ),
        status=status,
    )


def make_group(
    name: str,
    *,
    parent: str | None = None,
    managers: Iterable[str] = (),
    roles: Iterable[str] = (),
) -> Group:
    """Group displayed by its name."""
    return Group(
        api_version=API_VERSION,
        kind="Group",
        metadata=ObjectMeta(name=name, uid=uid(name)),
        spec=GroupSpec(
            display_name=name,
            parent_ref=ObjectRef(name=parent) if parent else None,
            manager_refs=refs(managers),
            role_refs=refs(roles),
        ),
    )


def make_invite(
    name: str = "invite",
    *,
    code: str = "CODE1234",
    groups: Iterable[str] = (),
    roles: Iterable[str] = (),
    use_count: int = -1,
    used: int = 0,
    valid_until: datetime | None = None,
    auto_approve: bool = False,
    resolved: bool | None = None,
) -> Invite:
    """Invite, with a ReferencesResolved condition unless resolved is None."""
    conditions = [] if resolved is None else [_resolved_condition(resolved)]
    return Invite(
        api_version=API_VERSION,
        kind="Invite",
        metadata=ObjectMeta(name=name, uid=uid(name)),
        spec=InviteSpec(
            code=code,
            group_refs=refs(groups),
            role_refs=refs(roles),
            use_count=use_count,
            valid_until=valid_until,
            auto_approve=auto_approve,
        ),
        status=InviteStatus(conditions=conditions, used=used),
    )


def _resolved_condition(resolved: bool) -> PlatformCondition:
    return condition(REFERENCES_RESOLVED_CONDITION, resolved, "Resolved" if resolved else "MissingReference")


def make_binding(name: str, *, user: str, namespace: str = "taky", synced: bool | None = None) -> UserBinding:
    """UserBinding, with a Synced condition unless synced is None."""
    status = None
    if synced is not None:
        status = UserBindingStatus(
            conditions=[condition(SYNCED_CONDITION, synced, "Provisioned" if synced else "Pending")]
        )
    return UserBinding(
        api_version=API_VERSION,
        kind="UserBinding",
        metadata=ObjectMeta(name=name, namespace=namespace, uid=uid(f"{namespace}/{name}"), generation=1),
        spec=UserBindingSpec(user_ref=ObjectRef(name=user)),
        status=status,
    )


def make_service(
    name: str, namespace: str, *, ports: Iterable[tuple[int, str, int | str]] = (), owner: str | None = None
) -> Service:
    """Service that selects app=<name>. A port is (port, protocol, targetPort). owner names the controlling Integration."""
    metadata = ObjectMeta(name=name, namespace=namespace, uid=uid(name))
    if owner is not None:
        metadata.owner_references = [
            OwnerReference(api_version=API_VERSION, kind="Integration", name=owner, uid=uid(owner), controller=True)
        ]
    return Service.model_validate(
        {
            "metadata": metadata,
            "spec": {
                "selector": {"app": name},
                "ports": [
                    {"port": port, "protocol": protocol, "targetPort": target} for port, protocol, target in ports
                ],
            },
        }
    )
