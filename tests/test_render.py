"""Rendered operator manifests: in sync with the code, hardened, and consistent with the package."""

import re
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

import yaml

from opendefence_core.k8s_operator.render import CRDS_PATH, IMAGE, OPERATOR_PATH, render
from opendefence_core.naming import OPERATOR_NAME, OPERATOR_TLS_SECRET, PUBLIC_CERT_NAMESPACE, SYSTEM_NAMESPACE

ROOT = Path(__file__).resolve().parents[1]


def _documents(path: Path) -> list[dict[str, Any]]:
    return list(yaml.safe_load_all(render()[path]))


def _kustomized() -> list[dict[str, Any]]:
    """The operator manifests as Zarf deploys them, hardened by manifests/operator/kustomization.yaml."""
    output = subprocess.run(  # nosec B603 B607
        ["kubectl", "kustomize", str(ROOT / OPERATOR_PATH.parent)], check=True, capture_output=True, text=True
    ).stdout
    return list(yaml.safe_load_all(output))


def _one(documents: list[dict[str, Any]], kind: str, namespace: str | None = None) -> dict[str, Any]:
    return next(
        document
        for document in documents
        if document["kind"] == kind and (namespace is None or document["metadata"].get("namespace") == namespace)
    )


def test_committed_manifests_are_current() -> None:
    """Run `task build:manifests` if this fails."""
    for path, content in render().items():
        assert (ROOT / path).read_text() == content, f"{path} is out of date, run `task build:manifests`"


def test_crds() -> None:
    """All five kinds, with the callsign rule on users."""
    crds = {document["metadata"]["name"]: document for document in _documents(CRDS_PATH)}
    assert set(crds) == {
        "users.platform.opendefence.fi",
        "groups.platform.opendefence.fi",
        "roles.platform.opendefence.fi",
        "invites.platform.opendefence.fi",
        "userbindings.platform.opendefence.fi",
    }
    schema = crds["users.platform.opendefence.fi"]["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    assert schema["x-kubernetes-validations"][0]["rule"] == "self.spec.callsign == self.metadata.name"


def test_operator_deployment_is_hardened() -> None:
    """Non-root, read-only, labelled, and started through the image entrypoint."""
    deployment = _one(_kustomized(), "Deployment")
    assert deployment["metadata"]["name"] == OPERATOR_NAME
    assert deployment["metadata"]["labels"]["app.kubernetes.io/part-of"] == "opendefence"
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert container["image"] == IMAGE
    assert "command" not in container
    assert container["args"] == ["operator", "run"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert {mount["name"] for mount in container["volumeMounts"]} == {"webhook-tls", "tmp"}
    volumes = {volume["name"]: volume for volume in pod["volumes"]}
    assert volumes["webhook-tls"]["secret"]["secretName"] == OPERATOR_TLS_SECRET


def test_operator_rbac() -> None:
    """Leases for leader election, read-only UserBindings, and the user certificate key pairs."""
    documents = _documents(OPERATOR_PATH)
    cluster_role = _one(documents, "ClusterRole")
    assert cluster_role["metadata"]["name"] == f"{OPERATOR_NAME}.{SYSTEM_NAMESPACE}"
    rules = {tuple(rule["resources"]): rule["verbs"] for rule in cluster_role["rules"]}
    assert rules[("userbindings",)] == ["get", "list", "watch"]
    assert ("userbindings/status",) not in rules
    assert "delete" in rules[("certificates",)]
    secrets = _one(documents, "Role", PUBLIC_CERT_NAMESPACE)
    assert secrets["rules"] == [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["delete", "get"]}]
    leases = _one(documents, "Role", SYSTEM_NAMESPACE)
    assert any(rule["resources"] == ["leases"] for rule in leases["rules"])


def test_webhooks_have_ca_injected() -> None:
    """cert-manager injects the webhook CA; Group writes and User deletes are validated."""
    webhook = _one(_kustomized(), "ValidatingWebhookConfiguration")
    annotations = webhook["metadata"]["annotations"]
    assert annotations["cert-manager.io/inject-ca-from"] == f"{SYSTEM_NAMESPACE}/{OPERATOR_TLS_SECRET}"
    assert all("caBundle" not in hook["clientConfig"] for hook in webhook["webhooks"])
    policies = {hook["rules"][0]["resources"][0]: hook["rules"][0] for hook in webhook["webhooks"]}
    assert set(policies) == {"groups", "users"}
    assert set(policies["groups"]["operations"]) == {"CREATE", "UPDATE", "DELETE"}
    assert policies["users"]["operations"] == ["DELETE"]


def test_api_runs_the_operator_image() -> None:
    """The API Deployment pins the same image as the operator; bump-my-version updates both."""
    deployment = (ROOT / "manifests" / "api" / "deployment.yaml").read_text()
    assert re.findall(r"image: (\S+)", deployment) == [IMAGE]
