"""Integration endpoints, with Kubernetes access replaced by fakes."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import ProductComponent, ProductDescription, ProductInfo
from opendefence_core.api.app import app
from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.uids import compact
from tests.factories import make_integration, make_user, uid
from tests.fakes import FakeList

client = TestClient(app)


def integration_id(name: str) -> str:
    """REST id of the integration the factories build under this name."""
    return compact(uid(name))


def _described() -> Integration:
    """An integration carrying full product info in two languages."""
    integration = make_integration("example", roles=["example-admin"], resolved=True)
    integration.spec.product_info = ProductInfo(
        icon="/ui/example/logo.svg",
        docs="https://docs.example.com/",
        component=ProductComponent(type="component", ref="/ui/example/remoteEntry.js"),
        descriptions=[
            ProductDescription(language="en", title="Example", description="An example product"),
            ProductDescription(language="fi", title="Esimerkki", description="Esimerkkituote"),
        ],
    )
    return integration


def _finnish_only() -> Integration:
    """An integration described only in Finnish."""
    integration = make_integration("example-two")
    integration.spec.product_info = ProductInfo(
        descriptions=[ProductDescription(language="fi", title="Example two", description="Esimerkkituote kaksi")],
    )
    return integration


@pytest.fixture
def integrations(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Integration]]:
    """One fully described integration, one Finnish only, and one with no product info."""
    store = [_described(), _finnish_only(), make_integration("example-three")]

    async def async_list(cls: type[Integration], **kwargs: object) -> FakeList[Integration]:
        _ = cls, kwargs
        return FakeList(store)

    monkeypatch.setattr(Integration, "async_list", classmethod(async_list))
    app.dependency_overrides[jwt_user] = lambda: make_user("user-1", callsign="alpha1")
    yield store
    app.dependency_overrides.clear()


def test_integrations_need_a_token() -> None:
    """The endpoints are authenticated."""
    assert client.get("/api/v3/integrations").status_code == 401


def test_read_integrations(integrations: list[Integration]) -> None:
    """Listing carries one card per installed product."""
    _ = integrations
    response = client.get("/api/v3/integrations")
    assert response.status_code == 200
    assert [(item["id"], item["name"]) for item in response.json()] == [
        (integration_id("example"), "example"),
        (integration_id("example-two"), "example-two"),
        (integration_id("example-three"), "example-three"),
    ]


def test_read_integration(integrations: list[Integration]) -> None:
    """A card holds what the UI draws, and nothing about roles or network policy."""
    _ = integrations
    body = client.get(f"/api/v3/integrations/{integration_id('example')}").json()
    assert body == {
        "id": integration_id("example"),
        "name": "example",
        "version": "1.0.0",
        "state": "ready",
        "title": "Example",
        "description": "An example product",
        "language": "en",
        "icon": "/ui/example/logo.svg",
        "docs": "https://docs.example.com/",
        "component": {"type": "component", "ref": "/ui/example/remoteEntry.js"},
    }


def test_read_integration_in_another_language(integrations: list[Integration]) -> None:
    """The asked-for language wins when the integration offers it."""
    _ = integrations
    body = client.get(f"/api/v3/integrations/{integration_id('example')}", params={"language": "fi"}).json()
    assert (body["language"], body["description"]) == ("fi", "Esimerkkituote")


def test_language_falls_back(integrations: list[Integration]) -> None:
    """An integration that lacks the language answers in what it has."""
    _ = integrations
    body = client.get(f"/api/v3/integrations/{integration_id('example-two')}", params={"language": "sv"}).json()
    assert (body["language"], body["title"]) == ("fi", "Example two")


def test_read_integration_without_product_info(integrations: list[Integration]) -> None:
    """An integration that declares no product info falls back to its display name."""
    _ = integrations
    body = client.get(f"/api/v3/integrations/{integration_id('example-three')}").json()
    assert (body["title"], body["description"], body["icon"], body["component"]) == ("example-three", "", None, None)


def test_version_comes_from_the_package(integrations: list[Integration]) -> None:
    """The declared version travels even when the integration describes no product."""
    _ = integrations
    body = client.get(f"/api/v3/integrations/{integration_id('example-three')}").json()
    assert body["version"] == "1.0.0"


def test_state_reports_what_the_operator_did(integrations: list[Integration]) -> None:
    """An integration the operator has not reported on is pending, not ready."""
    _ = integrations
    cards = {card["name"]: card["state"] for card in client.get("/api/v3/integrations").json()}
    assert cards == {"example": "ready", "example-two": "pending", "example-three": "pending"}


def test_unknown_integration(integrations: list[Integration]) -> None:
    """An id no integration holds is 404, and a bare name is 422."""
    _ = integrations
    assert client.get(f"/api/v3/integrations/{integration_id('missing')}").status_code == 404
    assert client.get("/api/v3/integrations/example").status_code == 422
