"""CRD generation for platform resources, and the examples that use them."""

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from cloudcoil.crd import CRD
from cloudcoil.resources import Resource

from lib_opendefence_core.models.v1alpha1 import API_VERSION, Group, Integration, Invite, Role, User, UserBinding

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
MODELS: dict[str, type[Resource]] = {
    "User": User,
    "Group": Group,
    "Role": Role,
    "Invite": Invite,
    "UserBinding": UserBinding,
    "Integration": Integration,
}


def _schema(model: type[Resource]) -> dict[str, Any]:
    return CRD(model).manifest()["spec"]["versions"][0]["schema"]["openAPIV3Schema"]


def test_library_import_boundary() -> None:
    library = Path(__file__).resolve().parents[2] / "src/lib_opendefence_core"
    for path in library.rglob("*.py"):
        tree = ast.parse(path.read_text())
        assert not any(
            (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("opendefence_core"))
            or (isinstance(node, ast.Import) and any(alias.name.startswith("opendefence_core") for alias in node.names))
            for node in ast.walk(tree)
        ), path


def _version(manifest: dict[str, Any]) -> dict[str, Any]:
    return manifest["spec"]["versions"][0]


def _column_names(manifest: dict[str, Any]) -> set[str]:
    return {column["name"] for column in _version(manifest).get("additionalPrinterColumns", [])}


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
    spec = _schema(User)["properties"]["spec"]["properties"]
    status = _schema(User)["properties"]["status"]["properties"]
    assert "publicKey" not in spec
    assert "publicKey" in status
    assert "roleRefs" in spec
    assert "callsign" in spec
    assert spec["callsign"]["pattern"] == r"^[A-Za-z0-9][A-Za-z0-9_]{2,29}$"
    assert spec["certificateApprovedAt"]["format"] == "date-time"
    assert "certificateApprovedAt" not in _schema(User)["properties"]["spec"]["required"]
    assert {"Callsign", "Revoked", "Approved", "Age"} <= _column_names(manifest)
    assert "bindings" in status


def test_user_callsign_can_change() -> None:
    """Callsign can change without changing the immutable resource name or UID."""
    assert "x-kubernetes-validations" not in _schema(User)


def test_userbinding_crd_is_namespaced_with_sync_columns() -> None:
    """UserBinding is namespaced, has a status subresource, and prints User/Synced."""
    manifest = CRD(UserBinding).manifest()
    assert manifest["metadata"]["name"] == "userbindings.platform.opendefence.fi"
    assert manifest["spec"]["group"] == "platform.opendefence.fi"
    assert manifest["spec"]["scope"] == "Namespaced"
    assert manifest["spec"]["names"]["shortNames"] == ["odub"]
    assert _version(manifest)["subresources"] == {"status": {}}
    assert "userRef" in _schema(UserBinding)["properties"]["spec"]["properties"]
    status = _schema(UserBinding)["properties"]["status"]["properties"]
    assert "conditions" in status
    assert "user" not in status
    assert {"User", "Synced", "Age"} <= _column_names(manifest)


@pytest.mark.parametrize(
    ("model", "plural", "short"),
    [
        (Group, "groups", "odgroup"),
        (Role, "roles", "odrole"),
        (Invite, "invites", "odinvite"),
        (Integration, "integrations", "odintegration"),
    ],
)
def test_group_role_invite_crds(model: type[Resource], plural: str, short: str) -> None:
    """Remaining kinds share the API group, cluster scope, and status subresource."""
    manifest = CRD(model).manifest()
    assert manifest["spec"]["group"] == API_VERSION.split("/")[0]
    assert manifest["spec"]["scope"] == "Cluster"
    assert manifest["spec"]["names"]["plural"] == plural
    assert manifest["spec"]["names"]["shortNames"] == [short]
    assert "status" in _version(manifest)["subresources"]


@pytest.mark.parametrize("model", [Group, Role, Integration])
def test_specs_do_not_repeat_metadata_name(model: type[Resource]) -> None:
    """These kinds are identified by metadata.name alone."""
    assert "name" not in _schema(model)["properties"]["spec"]["properties"]


@pytest.mark.parametrize("model", MODELS.values())
def test_all_custom_resource_fields_have_descriptions(model: type[Resource]) -> None:
    """Spec and status schemas describe every field exposed in the CRDs."""
    properties = _schema(model)["properties"]
    assert _missing_descriptions(properties["spec"], "spec") == []
    assert _missing_descriptions(properties["status"], "status") == []


def test_invite_status_does_not_duplicate_spec_references() -> None:
    """Invite status only reports common reconciliation state."""
    properties = _schema(Invite)["properties"]["status"]["properties"]
    assert "groups" not in properties
    assert "roles" not in properties


def _example_documents() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, document)
        for path in sorted(EXAMPLES.rglob("*.yaml"))
        for document in yaml.safe_load_all(path.read_text())
        if document is not None
    ]


def test_examples_parse_as_typed_resources() -> None:
    """Every example object validates against its model."""
    kinds: dict[str, int] = {}
    for path, document in _example_documents():
        if "kind" not in document:
            continue  # A patch, checked below
        parsed = MODELS[document["kind"]].model_validate(document)
        assert parsed.metadata is not None and parsed.metadata.name, path
        kinds[document["kind"]] = kinds.get(document["kind"], 0) + 1
    assert kinds == {"Role": 3, "Group": 1, "User": 2, "Invite": 4, "UserBinding": 1, "Integration": 1}


def test_approve_patch_applies_to_a_user() -> None:
    """examples/users/approve.yaml is a merge patch that approves a User."""
    patch = yaml.safe_load((EXAMPLES / "users" / "approve.yaml").read_text())
    user = next(document for _, document in _example_documents() if document.get("kind") == "User")
    approved = User.model_validate({**user, "spec": {**user["spec"], **patch["spec"]}})
    assert approved.spec.approved_at is not None
