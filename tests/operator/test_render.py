"""Rendered operator manifests: in sync with the code, hardened, and consistent with the package."""

import json
import re
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

import yaml

from opendefence_core.k8s_operator.render import CRDS_PATH, IMAGE, OPERATOR_PATH, render
from opendefence_core.naming import OPERATOR_NAME, OPERATOR_TLS_SECRET, PUBLIC_CERT_NAMESPACE, SYSTEM_NAMESPACE

ROOT = Path(__file__).resolve().parents[2]


def _documents(path: Path) -> list[dict[str, Any]]:
    return list(yaml.safe_load_all(render()[path]))


def _kustomized(path: Path = ROOT / OPERATOR_PATH.parent) -> list[dict[str, Any]]:
    """The operator manifests as Zarf deploys them, hardened by manifests/operator/kustomization.yaml."""
    output = subprocess.run(  # nosec B603 B607
        ["kubectl", "kustomize", str(path)], check=True, capture_output=True, text=True
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
    """All six kinds, with a mutable callsign on users."""
    crds = {document["metadata"]["name"]: document for document in _documents(CRDS_PATH)}
    assert set(crds) == {
        "users.platform.opendefence.fi",
        "groups.platform.opendefence.fi",
        "roles.platform.opendefence.fi",
        "invites.platform.opendefence.fi",
        "userbindings.platform.opendefence.fi",
        "integrations.platform.opendefence.fi",
    }
    schema = crds["users.platform.opendefence.fi"]["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    assert "x-kubernetes-validations" not in schema
    assert "callsign" in schema["properties"]["spec"]["properties"]


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


def test_certificate_settings_are_overridable(tmp_path: Path) -> None:
    """Kustomize changes both the configured lifetime and the Deployment's hashed reference."""
    package = yaml.safe_load((ROOT / "zarf.yaml").read_text())
    operator = next(component for component in package["components"] if component["name"] == "operator")
    assert operator["manifests"] == [{"name": "operator", "kustomizations": ["manifests/operator"]}]
    base = _kustomized()
    config = _one(base, "ConfigMap")
    assert config["data"] == {"USER_CERTIFICATE_DURATION": "2880h"}
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "resources": [str((ROOT / OPERATOR_PATH.parent).relative_to(tmp_path, walk_up=True))],
                "configMapGenerator": [
                    {
                        "name": "core-operator-config",
                        "namespace": SYSTEM_NAMESPACE,
                        "behavior": "merge",
                        "literals": ["USER_CERTIFICATE_DURATION=1440h"],
                    }
                ],
            }
        )
    )
    overlay = _kustomized(tmp_path)
    overridden = _one(overlay, "ConfigMap")
    assert overridden["data"]["USER_CERTIFICATE_DURATION"] == "1440h"
    assert overridden["metadata"]["name"] != config["metadata"]["name"]
    container = _one(overlay, "Deployment")["spec"]["template"]["spec"]["containers"][0]
    assert [source["configMapRef"]["name"] for source in container["envFrom"]] == [
        overridden["metadata"]["name"],
        "core-config",
    ]


def test_operator_rbac() -> None:
    """Leases for leader election, read-only UserBindings, and no access to private keys."""
    documents = _documents(OPERATOR_PATH)
    cluster_role = _one(documents, "ClusterRole")
    assert cluster_role["metadata"]["name"] == f"{OPERATOR_NAME}.{SYSTEM_NAMESPACE}"
    rules = {tuple(rule["resources"]): rule["verbs"] for rule in cluster_role["rules"]}
    assert rules[("userbindings",)] == ["get", "list", "watch"]
    assert ("userbindings/status",) not in rules
    assert ("certificates",) not in rules
    assert ("secrets",) not in rules
    assert "delete" in rules[("certificaterequests",)]
    assert not any(
        document["kind"] == "Role" and document["metadata"].get("namespace") == PUBLIC_CERT_NAMESPACE
        for document in documents
    )
    leases = _one(documents, "Role", SYSTEM_NAMESPACE)
    assert any(rule["resources"] == ["leases"] for rule in leases["rules"])


def test_webhooks_have_ca_injected() -> None:
    """cert-manager injects the webhook CA; Group writes, User callsigns and deletes are validated."""
    webhook = _one(_kustomized(), "ValidatingWebhookConfiguration")
    annotations = webhook["metadata"]["annotations"]
    assert annotations["cert-manager.io/inject-ca-from"] == f"{SYSTEM_NAMESPACE}/{OPERATOR_TLS_SECRET}"
    assert all("caBundle" not in hook["clientConfig"] for hook in webhook["webhooks"])
    policies = {
        (hook["rules"][0]["resources"][0], frozenset(hook["rules"][0]["operations"])) for hook in webhook["webhooks"]
    }
    assert policies == {
        ("groups", frozenset({"CREATE", "UPDATE", "DELETE"})),
        ("users", frozenset({"CREATE", "UPDATE"})),
        ("users", frozenset({"DELETE"})),
    }


def test_api_runs_the_operator_image() -> None:
    """The API Deployment pins the same image as the operator; bump-my-version updates both."""
    deployment = (ROOT / "manifests" / "api" / "deployment.yaml").read_text()
    assert re.findall(r"image: (\S+)", deployment) == [IMAGE]


def test_domain_value_fits_the_certificate_common_name() -> None:
    """Zarf rejects a domain whose first label is too long for CORE_DEPLOYMENT, before any pod starts."""
    schema = json.loads((ROOT / "values" / "values.schema.json").read_text())
    pattern = re.compile(schema["properties"]["domain"]["pattern"])
    for domain in ("opendefence.invalid", "local-dev.opendefence.fi", f"{'x' * 55}.example.org"):
        assert pattern.fullmatch(domain), domain
    for domain in (f"{'x' * 56}.example.org", "localhost", "-bad.example.org"):
        assert not pattern.fullmatch(domain), domain
