"""Projection of operator conditions into the state the API publishes."""

from lib_opendefence_core.models.v1alpha1 import REFERENCES_RESOLVED_CONDITION, PlatformStatus
from opendefence_core.api.lib.reconciliation import state_of
from tests.factories import condition


def status(*, resolved: bool, reason: str, observed: int | None = 1) -> PlatformStatus:
    """Status as a controller reports it once it has looked at the resource."""
    return PlatformStatus(
        conditions=[condition(REFERENCES_RESOLVED_CONDITION, resolved, reason)],
        observed_generation=observed,
    )


def test_missing_status_is_pending() -> None:
    """A resource the operator has not reported on yet is pending, not degraded."""
    assert state_of(None, 1) == "pending"


def test_empty_conditions_are_pending() -> None:
    """A status without the condition says nothing about the references."""
    assert state_of(PlatformStatus(observed_generation=1), 1) == "pending"


def test_resolved_references_are_ready() -> None:
    """The operator resolved everything the resource declares."""
    assert state_of(status(resolved=True, reason="Resolved"), 1) == "ready"


def test_missing_reference_is_pending() -> None:
    """An unresolved reference is the operator waiting, not the operator failing."""
    assert state_of(status(resolved=False, reason="MissingReference"), 1) == "pending"


def test_other_failures_are_degraded() -> None:
    """A failure the operator cannot wait out needs changed input."""
    assert state_of(status(resolved=False, reason="InvalidSpec"), 1) == "degraded"


def test_stale_status_is_pending() -> None:
    """A successful report about an older generation does not describe the current one."""
    assert state_of(status(resolved=True, reason="Resolved", observed=1), 2) == "pending"


def test_unset_generation_trusts_the_status() -> None:
    """Without a generation there is nothing to compare, so the condition decides."""
    assert state_of(status(resolved=True, reason="Resolved", observed=None), None) == "ready"
