"""Check the installed library wheel outside the checkout."""

import importlib.util
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

require(importlib.util.find_spec("opendefence_core") is None, "Application visible in library environment")

print("Installed library smoke test passed")
