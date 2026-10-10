"""Generated operator manifests stay in sync with the operator code."""

from pathlib import Path

import yaml

from opendefence_core.k8s_operator.render import CRDS_PATH, OPERATOR_PATH, render

ROOT = Path(__file__).resolve().parents[1]


def test_committed_manifests_are_current() -> None:
    """Run `task operator:manifests` if this fails."""
    for path, content in render().items():
        assert (ROOT / path).read_text() == content, f"{path} is out of date, run `task operator:manifests`"


def test_operator_manifests_are_hardened_and_ca_injected() -> None:
    """The Deployment runs non-root and read-only; cert-manager injects the webhook CA."""
    documents = list(yaml.safe_load_all(render()[OPERATOR_PATH]))
    deployment = next(document for document in documents if document["kind"] == "Deployment")
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert container["command"] == ["opendefence_core", "operator"]
    assert container["args"] == ["run"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    webhook = next(document for document in documents if document["kind"] == "ValidatingWebhookConfiguration")
    annotations = webhook["metadata"]["annotations"]
    assert annotations["cert-manager.io/inject-ca-from"] == "opendefence-system/operator-tls"
    assert all("caBundle" not in hook["clientConfig"] for hook in webhook["webhooks"])
    crds = [document["kind"] for document in yaml.safe_load_all(render()[CRDS_PATH])]
    assert crds == ["CustomResourceDefinition"] * 5
