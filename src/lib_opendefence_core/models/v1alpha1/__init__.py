"""platform.opendefence.fi/v1alpha1 resources."""

from lib_opendefence_core.models.v1alpha1.common import (
    API_VERSION,
    REFERENCES_RESOLVED_CONDITION,
    ObjectRef,
    PlatformStatus,
    ResolvedRef,
)
from lib_opendefence_core.models.v1alpha1.group import Group, GroupSpec, GroupStatus
from lib_opendefence_core.models.v1alpha1.integration import (
    Integration,
    IntegrationRole,
    IntegrationSpec,
    IntegrationStatus,
)
from lib_opendefence_core.models.v1alpha1.invite import Invite, InviteSpec, InviteStatus
from lib_opendefence_core.models.v1alpha1.role import Role, RoleSpec, RoleStatus
from lib_opendefence_core.models.v1alpha1.user import (
    ACCEPTED_CREDENTIALS_ANNOTATION,
    BINDINGS_SYNCED_CONDITION,
    CERTIFICATE_READY_CONDITION,
    BindingObservation,
    User,
    UserSpec,
    UserStatus,
)
from lib_opendefence_core.models.v1alpha1.userbinding import (
    SYNCED_CONDITION,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
    is_synced,
)

__all__ = [
    "ACCEPTED_CREDENTIALS_ANNOTATION",
    "API_VERSION",
    "BINDINGS_SYNCED_CONDITION",
    "CERTIFICATE_READY_CONDITION",
    "REFERENCES_RESOLVED_CONDITION",
    "SYNCED_CONDITION",
    "BindingObservation",
    "Group",
    "GroupSpec",
    "GroupStatus",
    "Integration",
    "IntegrationRole",
    "IntegrationSpec",
    "IntegrationStatus",
    "Invite",
    "InviteSpec",
    "InviteStatus",
    "ObjectRef",
    "PlatformStatus",
    "ResolvedRef",
    "Role",
    "RoleSpec",
    "RoleStatus",
    "User",
    "UserBinding",
    "UserBindingSpec",
    "UserBindingStatus",
    "UserSpec",
    "UserStatus",
    "is_synced",
]
