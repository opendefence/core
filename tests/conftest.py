"""pytest automagics"""

from __future__ import annotations

import logging
from typing import Any, Literal

from cloudcoil.errors import ResourceNotFound
from cloudcoil.resources import Resource

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


class FakeCache[T: Resource]:
    """In-memory stand-in for an informer snapshot."""

    def __init__(self, objects: dict[str, T] | None = None) -> None:
        self._objects = objects or {}

    def get(self, name: str, namespace: str | None = None) -> T | None:
        _ = namespace
        return self._objects.get(name)

    def list(self, namespace: str | None = None, *, all_namespaces: bool = False) -> list[T]:
        _ = namespace, all_namespaces
        return list(self._objects.values())


class FakeClient[T: Resource]:
    """In-memory stand-in for a typed API client; records deletes."""

    def __init__(self, objects: dict[tuple[str | None, str], T] | None = None) -> None:
        self._objects = objects or {}
        self.deleted: list[tuple[str | None, str]] = []

    async def get(self, name: str, namespace: str | None = None) -> T:
        key = (namespace, name)
        if key not in self._objects:
            raise ResourceNotFound(f"{namespace}/{name} not found")
        return self._objects[key]

    async def delete(self, name: str, namespace: str | None = None) -> T:
        key = (namespace, name)
        if key not in self._objects:
            raise ResourceNotFound(f"{namespace}/{name} not found")
        self.deleted.append(key)
        return self._objects.pop(key)


class FakeContext:
    """Narrow test double for Context status, cache and client operations."""

    def __init__(
        self,
        caches: dict[type[Resource], FakeCache[Resource]] | None = None,
        clients: dict[type[Resource], FakeClient[Resource]] | None = None,
    ) -> None:
        self._caches = caches or {}
        self.clients = clients or {}
        self.status: dict[str, Any] = {}
        self.conditions: list[tuple[str, bool | Literal["Unknown"], str, str]] = []
        self.ensured: list[Resource] = []

    async def client[U: Resource](self, resource: type[U]) -> FakeClient[U]:
        return self.clients.setdefault(resource, FakeClient())  # type: ignore[return-value]

    async def get[U: Resource](self, resource: type[U], name: str, *, namespace: str | None = None) -> U:
        client = await self.client(resource)
        return await client.get(name, namespace=namespace)

    async def ensure[U: Resource](self, desired: U) -> U:
        """Record the desired child; return the stored observed object if one is seeded."""
        self.ensured.append(desired)
        if desired.name is None:
            return desired
        client = await self.client(type(desired))
        try:
            return await client.get(desired.name, namespace=desired.namespace)
        except ResourceNotFound:
            return desired

    def cached[U: Resource](self, resource: type[U]) -> FakeCache[U]:
        cache = self._caches.get(resource)
        if cache is None:
            return FakeCache[U]()
        return cache  # type: ignore[return-value]

    def set_status(self, **changes: object) -> None:
        self.status.update(changes)

    def condition(self, name: str, status: bool | Literal["Unknown"], *, reason: str, message: str = "") -> None:
        self.conditions.append((name, status, reason, message))
