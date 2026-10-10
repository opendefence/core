"""CRD generation for platform resources."""

from pathlib import Path
from typing import Any

import yaml
from cloudcoil.crd import CRD

from opendefence_core.k8s_operator.models.v1alpha1 import API_VERSION, Group, Invite, Role, User, UserBinding


def _version(manifest: dict[str, Any]) -> dict[str, Any]:
    return manifest["spec"]["versions"][0]


def _column_names(manifest: dict[str, Any]) -> set[str]:
    return {column["name"] for column in _version(manifest).get("additionalPrinterColumns", [])}


def _spec_properties(manifest: dict[str, Any]) -> dict[str, Any]:
    return _version(manifest)["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]


def _status_properties(manifest: dict[str, Any]) -> dict[str, Any]:
    return _version(manifest)["schema"]["openAPIV3Schema"]["properties"]["status"]["properties"]


def _missing_descriptions(schema: dict[str, Any], path: str) -> list[str]:
    missing = [] if "description" in schema else [path]
    for name, child in schema.get("properties", {}).items():
        missing.extend(_missing_descriptions(child, f"{path}.{name}"))
    if "items" in schema:
        missing.extend(_missing_descriptions(schema["items"], f"{path}[]"))
    return missing


def test_user_crd_is_cluster_scoped_with_status_and_aliases() -> None:
    """User CRD is cluster-scoped, has a status subresource, and uses wire aliases."""
    manifest = CRD(User).manifest()
    assert manifest["metadata"]["name"] == "users.platform.opendefence.fi"
    assert manifest["spec"]["group"] == "platform.opendefence.fi"
    assert manifest["spec"]["scope"] == "Cluster"
    assert manifest["spec"]["names"]["shortNames"] == ["oduser"]
    assert _version(manifest)["name"] == "v1alpha1"
    assert _version(manifest)["subresources"] == {"status": {}}
    spec = _spec_properties(manifest)
    status = _status_properties(manifest)
    assert "publicKey" not in spec
    assert "publicKey" in status
    assert "roleRefs" in spec
    assert "callsign" in spec
    assert {"Callsign", "Revoked", "Approved", "Age"} <= _column_names(manifest)
    assert "bindings" in status


def test_userbinding_crd_is_namespaced_with_sync_columns() -> None:
    """UserBinding is namespaced, has a status subresource, and prints User/Synced."""
    manifest = CRD(UserBinding).manifest()
    assert manifest["metadata"]["name"] == "userbindings.platform.opendefence.fi"
    assert manifest["spec"]["group"] == "platform.opendefence.fi"
    assert manifest["spec"]["scope"] == "Namespaced"
    assert manifest["spec"]["names"]["shortNames"] == ["odub"]
    assert _version(manifest)["subresources"] == {"status": {}}
    spec = _spec_properties(manifest)
    status = _status_properties(manifest)
    assert "userRef" in spec
    assert "conditions" in status
    assert "user" not in status
    assert {"User", "Synced", "Age"} <= _column_names(manifest)


def test_group_role_invite_crds() -> None:
    """Remaining kinds share the API group, cluster scope, and status subresource."""
    for model, plural, short in (
        (Group, "groups", "odgroup"),
        (Role, "roles", "odrole"),
        (Invite, "invites", "odinvite"),
    ):
        manifest = CRD(model).manifest()
        assert manifest["spec"]["group"] == API_VERSION.split("/")[0]
        assert manifest["spec"]["scope"] == "Cluster"
        assert manifest["spec"]["names"]["plural"] == plural
        assert manifest["spec"]["names"]["shortNames"] == [short]
        assert "status" in _version(manifest)["subresources"]


def test_all_custom_resource_fields_have_descriptions() -> None:
    """Spec and status schemas describe every field exposed in the CRDs."""
    for model in (User, Group, Role, Invite, UserBinding):
        properties = _version(CRD(model).manifest())["schema"]["openAPIV3Schema"]["properties"]
        assert _missing_descriptions(properties["spec"], "spec") == []
        assert _missing_descriptions(properties["status"], "status") == []


def test_invite_status_does_not_duplicate_spec_references() -> None:
    """Invite status only reports common reconciliation state."""
    manifest = CRD(Invite).manifest()
    properties = _version(manifest)["schema"]["openAPIV3Schema"]["properties"]["status"]["properties"]
    assert "groups" not in properties
    assert "roles" not in properties


def test_demo_manifests_parse_as_typed_resources() -> None:
    """examples/demo.yaml round-trips through the handwritten resource models."""
    demo = Path(__file__).resolve().parents[1] / "examples" / "demo.yaml"
    kinds = {User: 0, Group: 0, Role: 0, Invite: 0, UserBinding: 0}
    models = {
        "User": User,
        "Group": Group,
        "Role": Role,
        "Invite": Invite,
        "UserBinding": UserBinding,
    }
    for document in yaml.safe_load_all(demo.read_text()):
        if document is None:
            continue
        model = models[document["kind"]]
        parsed = model.model_validate(document)
        kinds[model] += 1
        assert parsed.metadata is not None
        assert parsed.metadata.name
    assert kinds[Role] == 3
    assert kinds[Group] == 1
    assert kinds[User] == 2
    assert kinds[Invite] == 1
    assert kinds[UserBinding] == 1
