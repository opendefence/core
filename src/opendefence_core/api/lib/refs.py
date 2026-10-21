"""Helpers for the ObjectRef lists that platform specs hold."""

from collections.abc import Sequence

from lib_opendefence_core.models.v1alpha1 import ObjectRef


def names(name: str, refs: Sequence[ObjectRef]) -> bool:
    """Whether the refs name this object."""
    return any(ref.name == name for ref in refs)


def with_ref(refs: Sequence[ObjectRef], name: str) -> list[ObjectRef] | None:
    """Refs plus the name, or None when they already hold it."""
    if names(name, refs):
        return None
    return [*refs, ObjectRef(name=name)]


def without_ref(refs: Sequence[ObjectRef], name: str) -> list[ObjectRef] | None:
    """Refs without the name, or None when they do not hold it."""
    if not names(name, refs):
        return None
    return [ref for ref in refs if ref.name != name]
