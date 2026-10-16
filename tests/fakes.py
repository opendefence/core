"""In-memory stand-ins for cloudcoil clients, caches, contexts, and admission requests."""

from collections.abc import AsyncIterator, Iterable
from typing import Any, Literal, cast

from cloudcoil.apimachinery import ObjectMeta, OwnerReference
from cloudcoil.errors import ResourceConflict, ResourceNotFound
from cloudcoil.resources import Resource

type Key = tuple[str | None, str]


def _key(obj: Resource) -> Key:
    return (obj.namespace, obj.name or "")


class FakeList[T: Resource]:
    """Async-iterable stand-in for a live list result."""

    def __init__(self, items: list[T]) -> None:
        self.items = items

    async def __aiter__(self) -> AsyncIterator[T]:
        for item in self.items:
            yield item


class FakeClient[T: Resource]:
    """Typed API client over objects keyed by namespace and name; records deletes."""

    def __init__(self, objects: Iterable[T] = ()) -> None:
        self._objects: dict[Key, T] = {_key(obj): obj for obj in objects}
        self.deleted: list[Key] = []
        self.patches: list[list[dict[str, Any]]] = []

    async def get(self, name: str, namespace: str | None = None) -> T:
        if (namespace, name) not in self._objects:
            raise ResourceNotFound(f"{namespace}/{name} not found")
        return self._objects[(namespace, name)]

    async def delete(self, name: str, namespace: str | None = None, *, uid: str | None = None) -> T:
        if (namespace, name) not in self._objects:
            raise ResourceNotFound(f"{namespace}/{name} not found")
        existing = self._objects[(namespace, name)]
        if uid is not None and (not existing.metadata or existing.metadata.uid != uid):
            raise ResourceConflict("UID precondition failed")
        self.deleted.append((namespace, name))
        return self._objects.pop((namespace, name))

    async def patch(self, body: T, operations: list[dict[str, Any]]) -> T:
        """Apply the guarded metadata patches used by the operator."""
        current = await self.get(body.name or "", body.namespace)
        document = current.model_dump(mode="json", by_alias=True, exclude_none=True)
        for operation in operations:
            parts = [part.replace("~1", "/").replace("~0", "~") for part in operation["path"].split("/")[1:]]
            target = document
            for part in parts[:-1]:
                target = target[part]
            key = parts[-1]
            if operation["op"] == "test":
                if target.get(key) != operation["value"]:
                    raise ResourceConflict("Patch precondition failed")
            elif operation["op"] == "remove":
                del target[key]
            else:
                target[key] = operation["value"]
        document["metadata"]["resourceVersion"] = str(int(current.resource_version or "0") + 1)
        updated = cast(type[T], type(body)).model_validate(document)
        self._objects[_key(updated)] = updated
        self.patches.append(operations)
        return updated

    async def list(self, namespace: str | None = None, *, all_namespaces: bool = False) -> FakeList[T]:
        _ = namespace, all_namespaces
        return FakeList(list(self._objects.values()))


class FakeCache[T: Resource]:
    """Informer snapshot over objects keyed by namespace and name."""

    def __init__(self, objects: Iterable[T] = ()) -> None:
        self._objects: dict[Key, T] = {_key(obj): obj for obj in objects}

    def get(self, name: str, namespace: str | None = None) -> T | None:
        return self._objects.get((namespace, name))

    def list(self, namespace: str | None = None, *, all_namespaces: bool = False) -> list[T]:
        _ = namespace, all_namespaces
        return list(self._objects.values())


class FakeContext:
    """Reconcile Context with in-memory caches and clients that records status and conditions."""

    def __init__(
        self,
        caches: dict[type[Resource], FakeCache[Any]] | None = None,
        clients: dict[type[Resource], FakeClient[Any]] | None = None,
        parent: Resource | None = None,
    ) -> None:
        self._caches = caches or {}
        self.clients = clients or {}
        self.status: dict[str, Any] = {}
        self.conditions: list[tuple[str, bool | Literal["Unknown"], str, str]] = []
        self.ensured: list[Resource] = []
        self.parent = parent

    async def client[U: Resource](self, resource: type[U]) -> FakeClient[U]:
        return self.clients.setdefault(resource, FakeClient())

    async def get[U: Resource](self, resource: type[U], name: str, *, namespace: str | None = None) -> U:
        client = await self.client(resource)
        return await client.get(name, namespace=namespace)

    async def ensure[U: Resource](self, desired: U) -> U:
        """Persist desired fields and preserve the observed status of owned children."""
        self.ensured.append(desired)
        client = await self.client(type(desired))
        try:
            current = await client.get(desired.name or "", namespace=desired.namespace)
        except ResourceNotFound:
            current = desired.model_copy(deep=True)
            if current.metadata is None:
                current.metadata = ObjectMeta()
            current.metadata.uid = f"uid-{current.name}"
            if self.parent and self.parent.metadata:
                current.metadata.owner_references = [
                    OwnerReference(
                        api_version=self.parent.gvk().api_version,
                        kind=self.parent.gvk().kind,
                        name=self.parent.name or "",
                        uid=self.parent.metadata.uid or "",
                        controller=True,
                    )
                ]
        else:
            values = desired.model_dump(exclude_unset=True, exclude={"metadata"})
            current = cast(type[U], type(desired)).model_validate({**current.model_dump(), **values})
        client._objects[_key(current)] = current
        return current

    def cached[U: Resource](self, resource: type[U]) -> FakeCache[U]:
        return self._caches.get(resource) or FakeCache()

    def set_status(self, **changes: object) -> None:
        self.status.update(changes)

    def condition(self, name: str, status: bool | Literal["Unknown"], *, reason: str, message: str = "") -> None:
        self.conditions.append((name, status, reason, message))


class FakeAdmissionRequest[T: Resource]:
    """AdmissionRequest whose client reads the given objects; counts client lookups."""

    def __init__(
        self,
        *,
        operation: str = "CREATE",
        resource: T | None = None,
        old_resource: T | None = None,
        objects: Iterable[Resource] = (),
    ) -> None:
        self.operation = operation
        self.resource = resource
        self.old_resource = old_resource
        self.name = (old_resource.name if old_resource else None) or (resource.name if resource else None) or ""
        self._client: FakeClient[Resource] = FakeClient(objects)
        self.client_calls = 0

    async def client(self, resource: type[Resource]) -> FakeClient[Resource]:
        _ = resource
        self.client_calls += 1
        return self._client
