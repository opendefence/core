"""platform.opendefence.fi/v1alpha1 resources."""

from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION, ObjectRef, PlatformStatus, ResolvedRef
from opendefence_core.k8s_operator.models.v1alpha1.group import Group, GroupSpec, GroupStatus
from opendefence_core.k8s_operator.models.v1alpha1.invite import Invite, InviteSpec, InviteStatus
from opendefence_core.k8s_operator.models.v1alpha1.role import Role, RoleSpec, RoleStatus
from opendefence_core.k8s_operator.models.v1alpha1.user import (
    BINDINGS_SYNCED_CONDITION,
    CERTIFICATE_READY_CONDITION,
    BindingObservation,
    User,
    UserSpec,
    UserStatus,
)
from opendefence_core.k8s_operator.models.v1alpha1.userbinding import (
    SYNCED_CONDITION,
    UserBinding,
    UserBindingSpec,
    UserBindingStatus,
    is_synced,
)

__all__ = [
    "API_VERSION",
    "BINDINGS_SYNCED_CONDITION",
    "BindingObservation",
    "CERTIFICATE_READY_CONDITION",
    "Group",
    "GroupSpec",
    "GroupStatus",
    "Invite",
    "InviteSpec",
    "InviteStatus",
    "ObjectRef",
    "PlatformStatus",
    "ResolvedRef",
    "Role",
    "RoleSpec",
    "RoleStatus",
    "SYNCED_CONDITION",
    "User",
    "UserBinding",
    "UserBindingSpec",
    "UserBindingStatus",
    "UserSpec",
    "UserStatus",
    "is_synced",
]
