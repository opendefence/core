"""Publication retry rules."""

from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import nexus_publish


def test_retry_classifies_missing_identical_and_conflicting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = tmp_path / "library.whl"
    sdist = tmp_path / "library.tar.gz"
    wheel.write_bytes(b"same")
    sdist.write_bytes(b"new")

    def fetched(url: str) -> bytes:
        return {"same": b"same", "changed": b"old"}[url]

    monkeypatch.setattr(nexus_publish, "fetch", fetched)

    assert nexus_publish.missing_files([wheel, sdist], {wheel.name: "same"}) == [sdist]
    assert nexus_publish.missing_files([wheel], {wheel.name: "same"}) == []
    with pytest.raises(ValueError, match="Nexus artifact differs"):
        nexus_publish.missing_files([sdist], {sdist.name: "changed"})


def test_only_missing_package_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed_fetch(_url: str) -> bytes:
        raise HTTPError(nexus_publish.INDEX, 404, "missing", Message(), None)

    monkeypatch.setattr(nexus_publish, "fetch", failed_fetch)
    assert nexus_publish.remote_files() == {}

    def authentication_failure(_url: str) -> bytes:
        raise HTTPError(nexus_publish.INDEX, 401, "unauthorized", Message(), None)

    monkeypatch.setattr(nexus_publish, "fetch", authentication_failure)
    with pytest.raises(HTTPError) as error:
        nexus_publish.remote_files()
    assert error.value.code == 401


def test_index_links_resolve_within_nexus(monkeypatch: pytest.MonkeyPatch) -> None:
    def page(_url: str) -> bytes:
        return b'<a href="../../packages/lib/a.whl#sha256=abc">a.whl</a>'

    monkeypatch.setattr(nexus_publish, "fetch", page)
    assert nexus_publish.remote_files() == {
        "a.whl": "https://nexus.dev.pvarki.fi/repository/pypilocal/packages/lib/a.whl#sha256=abc"
    }

    def external_page(_url: str) -> bytes:
        return b'<a href="https://other.example/a.whl">a</a>'

    monkeypatch.setattr(nexus_publish, "fetch", external_page)
    with pytest.raises(ValueError, match="external artifact URL"):
        nexus_publish.remote_files()
