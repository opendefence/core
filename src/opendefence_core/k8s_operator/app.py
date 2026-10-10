"""Cloudcoil application for OpenDefence platform entities."""

import os

from cloudcoil.application import Application, RBACRule, WebhookServer
from cloudcoil.controller import HealthServer
from cloudcoil.models.cert_manager.v1 import Certificate
from cloudcoil.models.kubernetes.core.v1 import Secret

from opendefence_core.k8s_operator.controllers import ALL_CONTROLLERS
from lib_opendefence_core.models.v1alpha1 import UserBinding
from opendefence_core.naming import OPERATOR_NAME, OPERATOR_TLS_SECRET, PUBLIC_CERT_NAMESPACE, SYSTEM_NAMESPACE

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
        RBACRule(Certificate, verbs=("delete",), plural="certificates", scope="Namespaced", all_namespaces=True),
        # Read the issued key pair, and delete it on revoke so re-approval gets a new key
        RBACRule(
            Secret, verbs=("get", "delete"), plural="secrets", scope="Namespaced", namespace=PUBLIC_CERT_NAMESPACE
        ),
    ),
)
for controller in ALL_CONTROLLERS:
    app.include(controller)
