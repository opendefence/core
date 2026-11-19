"""Fixtures shared by the API tests."""

import pytest

from lib_opendefence_core.models.v1alpha1 import User
from tests.fakes import FakeList


@pytest.fixture
def users(monkeypatch: pytest.MonkeyPatch) -> list[User]:
    """Users the API can list."""
    state: list[User] = []

    async def async_list(cls: type[User], **kwargs: object) -> FakeList[User]:
        _ = cls, kwargs
        return FakeList(state)

    monkeypatch.setattr(User, "async_list", classmethod(async_list))
    return state
