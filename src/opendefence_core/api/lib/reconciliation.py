"""How far the operator has got with a resource's desired state."""

from typing import Literal

from lib_opendefence_core.models.v1alpha1 import REFERENCES_RESOLVED_CONDITION, PlatformStatus

type ReconciliationState = Literal["ready", "pending", "degraded"]

# The operator waits on these rather than failing
WAITING_REASONS = frozenset({"MissingReference"})


def state_of(status: PlatformStatus | None, generation: int | None) -> ReconciliationState:
    """State of the current generation."""
    if status is None:
        return "pending"
    if generation is not None and status.observed_generation != generation:
        return "pending"
    resolved = next((item for item in status.conditions if item.type == REFERENCES_RESOLVED_CONDITION), None)
    if resolved is None:
        return "pending"
    if resolved.status == "True":
        return "ready"
    return "pending" if resolved.reason in WAITING_REASONS else "degraded"
