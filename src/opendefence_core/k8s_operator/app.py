"""Cloudcoil application for OpenDefence platform entities."""

import os

from cloudcoil.application import Application, RBACRule, WebhookServer
from cloudcoil.controller import HealthServer
from cloudcoil.models.cert_manager.v1 import CertificateRequest

from lib_opendefence_core.models.v1alpha1 import Role, UserBinding
from opendefence_core.k8s_operator.controllers import ALL_CONTROLLERS
from opendefence_core.naming import OPERATOR_NAME, OPERATOR_TLS_SECRET, SYSTEM_NAMESPACE

HEALTH_PORT = 8080

app = Application(
    OPERATOR_NAME,
    # The Deployment sets CLOUDCOIL_NAMESPACE to its own namespace
    namespace=os.environ.get("CLOUDCOIL_NAMESPACE", SYSTEM_NAMESPACE),
    leader_election=True,
    health=HealthServer(host="0.0.0.0", port=HEALTH_PORT),  # nosec B104
    webhook=WebhookServer(tls_secret=OPERATOR_TLS_SECRET),
    resources=(UserBinding,),
    rules=(
        # Owning Roles grants create and patch; delete covers roles an Integration drops
        RBACRule(Role, verbs=("delete",)),
        RBACRule(
            CertificateRequest, verbs=("delete",), plural="certificaterequests", scope="Namespaced", all_namespaces=True
        ),
    ),
)
for controller in ALL_CONTROLLERS:
    app.include(controller)
