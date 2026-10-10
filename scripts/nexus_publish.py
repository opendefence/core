"""Publish missing library artifacts; reject changed artifacts on retry."""

import base64
import hashlib
import os
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

INDEX = "https://nexus.dev.pvarki.fi/repository/pypilocal/simple/lib-opendefence-core/"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href" and value is not None)


def fetch(url: str) -> bytes:
    if (
        urllib.parse.urlsplit(url).scheme != "https"
        or urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(INDEX).netloc
    ):
        raise ValueError(f"Nexus URL is outside the HTTPS repository: {url}")
    credentials = f"{os.environ['TWINE_USERNAME']}:{os.environ['TWINE_PASSWORD']}".encode()
    header = "Basic " + base64.b64encode(credentials).decode()
    request = urllib.request.Request(url, headers={"Authorization": header})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - URL scheme and host checked above
        return response.read()


def remote_files() -> dict[str, str]:
    try:
        page = fetch(INDEX).decode()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise
    links = Links()
    links.feed(page)
    result = {}
    for href in links.hrefs:
        url = urllib.parse.urljoin(INDEX, href)
        if (
            urllib.parse.urlsplit(url).scheme != "https"
            or urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(INDEX).netloc
        ):
            raise ValueError(f"Nexus returned an external artifact URL: {url}")
        name = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).name
        result[name] = url
    return result


def missing_files(files: list[Path], remote: dict[str, str]) -> list[Path]:
    missing = []
    for path in files:
        if path.name not in remote:
            missing.append(path)
        elif hashlib.sha256(fetch(remote[path.name])).digest() != hashlib.sha256(path.read_bytes()).digest():
            raise ValueError(f"Nexus artifact differs: {path.name}; bump the release version")
    return missing


def main() -> None:
    version = tomllib.loads(Path(".bumpversion.toml").read_text())["tool"]["bumpversion"]["current_version"]
    directory = Path(sys.argv[1])
    files = sorted(directory.iterdir())
    expected = {f"lib_opendefence_core-{version}.tar.gz", f"lib_opendefence_core-{version}-py3-none-any.whl"}
    if {path.name for path in files} != expected:
        raise ValueError(f"Expected only library artifacts at {version}: {directory}")
    missing = missing_files(files, remote_files())
    for path in missing:
        print(path)


if __name__ == "__main__":
    main()
