"""The REST identifier: a Kubernetes uid in compact form.

Clients may send either form. The API emits the compact one only.
"""

import base64
from typing import Annotated
from uuid import UUID

from cloudcoil.resources import Resource
from fastapi import Path
from pydantic import AfterValidator, Field

COMPACT_LENGTH = 22
"""Characters in the compact form: 16 raw bytes as unpadded Base64URL."""

COMPACT_PATTERN = r"[A-Za-z0-9_-]{21}[AQgw]"
CANONICAL_PATTERN = r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}"
ID_PATTERN = rf"^(?:{CANONICAL_PATTERN}|{COMPACT_PATTERN})$"


def compact(uid: str) -> str:
    """The uid as 22 unpadded Base64URL characters, the only form the API emits."""
    return base64.urlsafe_b64encode(UUID(uid).bytes).decode().rstrip("=")


def canonical(value: str) -> str:
    """The uid behind either accepted form, as Kubernetes stores it."""
    if len(value) == COMPACT_LENGTH:
        return str(UUID(bytes=base64.urlsafe_b64decode(f"{value}==")))
    return str(UUID(value))


ObjectId = Annotated[str, Path(pattern=ID_PATTERN), AfterValidator(canonical)]
"""Path parameter naming a platform object. The handler receives the canonical uid."""

RefId = Annotated[str, Field(pattern=ID_PATTERN), AfterValidator(canonical)]
"""Body field naming another platform object. The model receives the canonical uid."""


def id_of(obj: Resource) -> str:
    """REST id of a stored object."""
    uid = obj.metadata.uid if obj.metadata else None
    if uid is None:
        raise ValueError(f"{type(obj).__name__} has no uid")
    return compact(uid)


async def by_uid[T: Resource](kind: type[T], uid: str) -> T | None:
    """Object with the uid, or None.

    Kubernetes has no uid field selector for custom resources, so this lists
    the kind and scans it.
    """
    async for obj in await kind.async_list():
        if obj.metadata is not None and obj.metadata.uid == uid:
            return obj
    return None


async def ids_by_name[T: Resource](kind: type[T]) -> dict[str, str]:
    """Ids of every object of the kind, keyed by name, to resolve the refs specs hold."""
    return {obj.name: id_of(obj) async for obj in await kind.async_list() if obj.name}
