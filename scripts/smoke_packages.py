"""Run from outside the checkout with installed release wheels."""

import importlib.util
import sys
from importlib.metadata import version

from cloudcoil.crd import CRD

from lib_opendefence_core import __version__
from lib_opendefence_core.models.v1alpha1 import Group, Invite, Role, User, UserBinding


def require(valid: bool, detail: str) -> None:
    if not valid:
        raise ValueError(detail)


require(version("lib-opendefence-core") == __version__, "Library version differs")
for model in (Group, Invite, Role, User, UserBinding):
    require(CRD(model).manifest()["spec"]["group"] == "platform.opendefence.fi", f"Wrong CRD group: {model}")
user = User.model_validate(
    {
        "apiVersion": "platform.opendefence.fi/v1alpha1",
        "kind": "User",
        "metadata": {"name": "abc"},
        "spec": {"callsign": "abc"},
    }
)
require(user.model_dump(by_alias=True)["spec"]["callsign"] == "abc", "User serialization failed")

if sys.argv[1] == "library":
    require(importlib.util.find_spec("opendefence_core") is None, "Application visible in library environment")
else:
    require(version("opendefence-core") == __version__, "Application version differs")
    from opendefence_core.api.app import app as api
    from opendefence_core.cli.console import opendefence_core_cli
    from opendefence_core.k8s_operator.app import app as operator

    require(api.version == __version__, "API version differs")
    require(bool(opendefence_core_cli.name), "CLI import failed")
    require(bool(operator.webhook), "Operator import failed")

print(f"Installed {sys.argv[1]} smoke test passed")
