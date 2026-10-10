"""Offline Application manifests."""

from dataclasses import replace

from opendefence_core.k8s_operator.app import app

TEST_CA_PEM = b"-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n"


def test_manifests_include_crds_and_leader_election_rbac() -> None:
    """Generated manifests install the CRDs and lease permissions."""
    documents = app.manifests(include_webhooks=False)
    kinds: dict[str, list[str]] = {}
    for document in documents:
        kinds.setdefault(document["kind"], []).append(document["metadata"]["name"])
    assert set(kinds["CustomResourceDefinition"]) == {
        "users.platform.opendefence.fi",
        "groups.platform.opendefence.fi",
        "roles.platform.opendefence.fi",
        "invites.platform.opendefence.fi",
        "userbindings.platform.opendefence.fi",
    }
    assert "opendefence-platform" in kinds["ServiceAccount"]
    assert "opendefence-platform.opendefence-system" in kinds["ClusterRole"]
    cluster_role = next(document for document in documents if document["kind"] == "ClusterRole")
    userbinding_rule = next(rule for rule in cluster_role["rules"] if rule.get("resources") == ["userbindings"])
    assert userbinding_rule["verbs"] == ["get", "list", "watch"]
    assert not any(rule.get("resources") == ["userbindings/status"] for rule in cluster_role["rules"])
    role = next(
        document
        for document in documents
        if document["kind"] == "Role" and document["metadata"]["namespace"] == "opendefence-system"
    )
    resources = [rule.get("resources") for rule in role["rules"]]
    assert any(resource == ["leases"] for resource in resources)
    assert "ValidatingWebhookConfiguration" not in kinds
    assert "Service" not in kinds


def test_manifests_include_group_validating_webhook() -> None:
    """TLS-backed manifests register Group CREATE/UPDATE/DELETE admission."""
    original = app.webhook
    assert original is not None
    app.webhook = replace(original, ca_bundle=TEST_CA_PEM)
    try:
        documents = app.manifests(image="example.invalid/opendefence-core:test")
    finally:
        app.webhook = original
    kinds = {document["kind"] for document in documents}
    assert "ValidatingWebhookConfiguration" in kinds
    assert "Service" in kinds
    assert "Deployment" in kinds
    webhook = next(document for document in documents if document["kind"] == "ValidatingWebhookConfiguration")
    policies = {policy["rules"][0]["resources"][0]: policy for policy in webhook["webhooks"]}
    assert set(policies) == {"groups", "users"}
    assert set(policies["groups"]["rules"][0]["operations"]) == {"CREATE", "UPDATE", "DELETE"}
    assert policies["groups"]["rules"][0]["apiGroups"] == ["platform.opendefence.fi"]
    assert policies["users"]["rules"][0]["operations"] == ["DELETE"]
    deployment = next(document for document in documents if document["kind"] == "Deployment")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    assert container["volumeMounts"][0]["name"] == "webhook-tls"
    assert pod_spec["volumes"][0]["secret"]["secretName"] == original.tls_secret
