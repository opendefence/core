"""Check the library distribution before publication."""

import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.requirements import Requirement

from lib_opendefence_core import __version__ as library_version
from opendefence_core import __version__ as application_version

ROOT = Path(__file__).resolve().parents[1]
DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")


def read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def require(valid: bool, detail: str) -> None:
    if not valid:
        raise ValueError(detail)


root = read_toml(ROOT / "pyproject.toml")
library = read_toml(ROOT / "src/lib_opendefence_core/pyproject.toml")
lock = read_toml(ROOT / "uv.lock")
version = read_toml(ROOT / ".bumpversion.toml")["tool"]["bumpversion"]["current_version"]
require(root["project"]["version"] == library["project"]["version"] == version, "Project versions differ")
require(application_version == library_version == version, "Runtime versions differ")
workspace = {p["name"]: p for p in lock["package"] if p["name"] in {"opendefence-core", "lib-opendefence-core"}}
require(
    {name: package["version"] for name, package in workspace.items()}
    == {"opendefence-core": version, "lib-opendefence-core": version},
    "Lockfile versions differ",
)
require(
    workspace["opendefence-core"]["source"] == {"editable": "."}
    and workspace["lib-opendefence-core"]["source"] == {"editable": "src/lib_opendefence_core"},
    "Lockfile workspace sources differ",
)
requirements = [Requirement(value) for value in root["project"]["dependencies"]]
require(
    [str(item.specifier) for item in requirements if item.name == "lib-opendefence-core"] == [f"=={version}"],
    "Application library requirement differs",
)

(wheel,) = DIST.glob(f"lib_opendefence_core-{version}-*.whl")
sdist = DIST / f"lib_opendefence_core-{version}.tar.gz"
require(sdist.is_file(), f"Missing {sdist}")
with zipfile.ZipFile(wheel) as archive:
    files = archive.namelist()
    package_files = [name for name in files if ".dist-info/" not in name]
    require(
        bool(package_files) and all(name.startswith("lib_opendefence_core/") for name in package_files),
        f"Wrong wheel files: {wheel}",
    )
    require("lib_opendefence_core/py.typed" in files, f"Missing py.typed: {wheel}")
    (metadata_file,) = (name for name in files if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser().parsebytes(archive.read(metadata_file))
    require(metadata["Version"] == version, f"Wrong wheel version: {wheel}")
    require(metadata["Name"] == "lib-opendefence-core", f"Wrong wheel name: {wheel}")
with tarfile.open(sdist) as archive:
    files = archive.getnames()
    require(any(name.endswith("/pyproject.toml") for name in files), f"Missing pyproject.toml: {sdist}")
    require(any(name.endswith("/py.typed") for name in files), f"Missing py.typed: {sdist}")

print(f"Validated library distribution at {version}")
