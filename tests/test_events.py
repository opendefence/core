"""Event recording for cluster-scoped platform objects."""

from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import httpx
from cloudcoil.client import Config

from opendefence_core.k8s_operator.controllers._events import recorder
from tests.factories import make_user


def _config(namespace: str) -> Any:
    response = Mock(spec=httpx.Response)
    response.is_success = True
    response.status_code = 201
    config = Mock()
    config.server = "https://example.invalid"
    config.namespace = namespace
    config.async_client.post = AsyncMock(return_value=response)
    return config


async def test_cluster_scoped_events_use_operator_namespace() -> None:
    """Cluster-scoped Events live in the operator namespace and name it on regarding."""
    config = _config("opendefence-system")
    user = make_user("bob")

    assert await recorder("users").emit(user, "Reconciled", "ok", config=cast(Config, config))
    assert user.namespace is None

    posted = config.async_client.post
    posted.assert_awaited_once()
    path, body = posted.call_args.args[0], posted.call_args.kwargs["json"]
    assert path == "/apis/events.k8s.io/v1/namespaces/opendefence-system/events"
    assert body["metadata"]["namespace"] == "opendefence-system"
    assert body["regarding"]["namespace"] == "opendefence-system"
    assert body["regarding"]["name"] == "bob"
    assert user.metadata is not None
    assert body["regarding"]["uid"] == user.metadata.uid


async def test_namespaced_events_keep_object_namespace() -> None:
    """Namespaced objects keep Events in their own namespace."""
    config = _config("opendefence-system")
    user = make_user("bob", namespace="team-a")

    assert await recorder("users").emit(user, "Reconciled", "ok", config=cast(Config, config))
    path = config.async_client.post.call_args.args[0]
    body = config.async_client.post.call_args.kwargs["json"]
    assert path == "/apis/events.k8s.io/v1/namespaces/team-a/events"
    assert body["metadata"]["namespace"] == "team-a"
    assert body["regarding"]["namespace"] == "team-a"
    assert user.namespace == "team-a"
