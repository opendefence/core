"""Check the library distribution before publication."""

import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")


def read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def require(valid: bool, detail: str) -> None:
    if not valid:
        raise ValueError(detail)


root = read_toml(ROOT / "pyproject.toml")
library = read_toml(ROOT / "src/lib_opendefence_core/pyproject.toml")
version = read_toml(ROOT / ".bumpversion.toml")["tool"]["bumpversion"]["current_version"]
require(root["project"]["version"] == library["project"]["version"] == version, "Project versions differ")

(wheel,) = DIST.glob(f"lib_opendefence_core-{version}-*.whl")
with zipfile.ZipFile(wheel) as archive:
    require("lib_opendefence_core/py.typed" in archive.namelist(), f"Missing py.typed: {wheel}")

print(f"Validated library distribution at {version}")
