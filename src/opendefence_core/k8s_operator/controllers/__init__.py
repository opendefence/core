"""Controller groups included by the platform operator."""

from typing import Any

from cloudcoil.controller import Controller

from opendefence_core.k8s_operator.controllers.groups import groups
from opendefence_core.k8s_operator.controllers.invites import invites
from opendefence_core.k8s_operator.controllers.roles import roles
from opendefence_core.k8s_operator.controllers.users import users

ALL_CONTROLLERS: tuple[Controller[Any], ...] = (users, groups, roles, invites)

__all__ = ["ALL_CONTROLLERS", "groups", "invites", "roles", "users"]
