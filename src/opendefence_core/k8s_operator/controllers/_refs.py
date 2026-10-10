"""Resolve name refs from informer snapshots and map reverse dependencies."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn, Protocol

from cloudcoil.controller import ResourceKey, TerminalError, Wait
from cloudcoil.resources import Resource

from opendefence_core.k8s_operator.models.v1alpha1.common import ObjectRef, ResolvedRef

type ResourceRefs = Sequence[ObjectRef] | ObjectRef | None


class CachedStore[T: Resource](Protocol):
    """Subset of CachedResources used by reference resolution."""

    def get(self, name: str, namespace: str | None = None) -> T | None: ...


class RefContext(Protocol):
    """Subset of Context used by reference resolution."""

    def cached[U: Resource](self, resource: type[U]) -> CachedStore[U]: ...

    def condition(self, name: str, status: bool | Literal["Unknown"], *, reason: str, message: str = "") -> None: ...


def ref_names(refs: ResourceRefs) -> list[str]:
    """Return the object names referenced by a field."""
    if refs is None:
        return []
    if isinstance(refs, ObjectRef):
        return [refs.name]
    return [ref.name for ref in refs]


def referrers_of[T: Resource](
    objects: Sequence[T],
    refs_of: Callable[[T], ResourceRefs],
    target: Resource,
) -> list[ResourceKey]:
    """Return primary keys whose refs include the target object's name."""
    target_name = target.name
    if not target_name:
        return []
    keys: list[ResourceKey] = []
    for obj in objects:
        if obj.name and target_name in ref_names(refs_of(obj)):
            keys.append(ResourceKey(obj.name, obj.namespace))
    return keys


@dataclass(frozen=True)
class ParentChainIssue:
    """Why a parentRef chain is not a tree."""

    reason: Literal["SelfReference", "CycleDetected", "MissingReference"]
    message: str


async def inspect_parent_chain[T](
    name: str | None,
    parent: str | None,
    get: Callable[[str], Awaitable[T | None]],
    parent_of: Callable[[T], str | None],
) -> ParentChainIssue | None:
    """Walk upward from parentRef and report self-reference, cycles, or missing ancestors."""
    if parent is None:
        return None
    if name is not None and parent == name:
        return ParentChainIssue("SelfReference", "parentRef must not refer to the same object")
    seen: set[str] = {name} if name else set()
    path: list[str] = [name] if name else []
    current = parent
    while current is not None:
        path.append(current)
        if current in seen:
            joined = " -> ".join(path)
            return ParentChainIssue("CycleDetected", f"parentRef would create a cycle: {joined}")
        seen.add(current)
        obj = await get(current)
        if obj is None:
            return ParentChainIssue("MissingReference", f"Group not found: {current}")
        current = parent_of(obj)
    return None


def reject_parent_chain_issue(ctx: RefContext, issue: ParentChainIssue) -> NoReturn:
    """Fail reconcile when the parent chain is cyclic or an ancestor is missing."""
    ctx.condition("ReferencesResolved", False, reason=issue.reason, message=issue.message)
    if issue.reason == "MissingReference":
        raise Wait("MissingReference", issue.message, after=60)
    raise TerminalError(issue.message)


def resolve_refs[T: Resource](
    ctx: RefContext,
    kind: type[T],
    refs: Sequence[ObjectRef],
) -> list[ResolvedRef]:
    """Resolve name refs from the informer cache, or wait until they exist."""
    resolved: list[ResolvedRef] = []
    missing: list[str] = []
    cache = ctx.cached(kind)
    for ref in refs:
        obj = cache.get(ref.name)
        uid = obj.metadata.uid if obj is not None and obj.metadata is not None else None
        if not uid:
            missing.append(ref.name)
            continue
        resolved.append(ResolvedRef(name=ref.name, uid=uid))
    if missing:
        message = f"{kind.__name__} not found: {', '.join(missing)}"
        ctx.condition("ReferencesResolved", False, reason="MissingReference", message=message)
        raise Wait("MissingReference", message, after=60)
    return resolved


def resolve_optional_ref[T: Resource](
    ctx: RefContext,
    kind: type[T],
    ref: ObjectRef | None,
) -> ResolvedRef | None:
    """Resolve a single optional name ref, or wait until it exists."""
    if ref is None:
        return None
    return resolve_refs(ctx, kind, [ref])[0]


def mark_resolved(ctx: RefContext) -> None:
    """Record that every declared reference was resolved."""
    ctx.condition("ReferencesResolved", True, reason="Resolved")
