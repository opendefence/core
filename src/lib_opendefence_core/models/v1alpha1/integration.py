"""Integration custom resource."""

from typing import Annotated, Literal

from cloudcoil.crd import ListType, PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource
from pydantic import Field

from lib_opendefence_core.models.v1alpha1.common import API_VERSION, PlatformStatus

# An extra role's name becomes Role metadata.name
ROLE_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


class IntegrationRole(BaseModel):
    """A platform role created for an integration."""

    name: str = Field(
        min_length=1,
        max_length=63,
        pattern=ROLE_NAME_PATTERN,
        description="Kubernetes resource name of the Role this integration adds.",
    )
    display_name: str = Field(
        min_length=1,
        alias="displayName",
        description="Human-readable name of the role.",
    )


class ProductComponent(BaseModel):
    """How the product is opened in the platform UI."""

    type: Literal["link", "markdown", "component"] = Field(
        description="Whether ref is a link, a markdown document, or a UI component.",
    )
    ref: str = Field(
        min_length=1,
        description="URL, markdown path, or component reference for the product.",
    )


class ProductDescription(BaseModel):
    """Localized title and description of the product."""

    language: str = Field(
        min_length=1,
        description="Language of this title and description, such as en or fi.",
    )
    title: str = Field(
        min_length=1,
        description="Human-readable product title in this language.",
    )
    description: str = Field(
        min_length=1,
        description="Short description of the product in this language.",
    )


class ProductInfo(BaseModel):
    """Presentation of the integration in the platform UI."""

    icon: str | None = Field(
        default=None,
        description="URL of the product icon.",
    )
    docs: str | None = Field(
        default=None,
        description="URL of the product documentation.",
    )
    component: ProductComponent | None = Field(
        default=None,
        description="How the product is opened in the platform UI.",
    )
    descriptions: Annotated[list[ProductDescription], ListType("map", keys=("language",))] = Field(
        default_factory=list,
        description="Localized titles and descriptions, one entry per language.",
    )


class IntegrationNetworkPolicy(BaseModel):
    """Intended traffic for the integration. Core stores it and does not enforce it."""

    ingress: Literal["Local", "Cluster", "Public"] = Field(
        default="Local",
        description="Who may connect in: Local is the integration namespace, Cluster is the cluster, Public is outside.",
    )
    egress: Literal["Local", "Cluster", "Internet"] = Field(
        default="Internet",
        description="Where the integration may connect: Local is its namespace, Cluster is the cluster, Internet is outside.",
    )


class IntegrationSpec(BaseModel):
    """Desired identity, product info, roles, and network policy of an integration."""

    display_name: Annotated[str, PrinterColumn(name="Display name")] = Field(
        min_length=1,
        alias="displayName",
        description="Human-readable name of the integration.",
    )
    version: Annotated[str, PrinterColumn(name="Version")] = Field(
        min_length=1,
        description="Version of the integration.",
    )
    product_info: ProductInfo | None = Field(
        default=None,
        alias="productInfo",
        description="How the integration is presented in the platform UI.",
    )
    additional_metadata: str | None = Field(
        default=None,
        alias="additionalMetadata",
        description="Extra information about the integration, stored as text.",
    )
    extra_roles: Annotated[list[IntegrationRole], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        alias="extraRoles",
        description="Roles this integration adds. The operator creates each as a cluster Role.",
    )
    network_policy: IntegrationNetworkPolicy = Field(
        default_factory=IntegrationNetworkPolicy,
        alias="networkPolicy",
        description="Intended ingress and egress. Core stores this and does not enforce it yet.",
    )


class IntegrationStatus(PlatformStatus):
    """Ready conditions for an integration. Integrations have no outgoing references."""


@custom_resource(
    api_version=API_VERSION,
    plural="integrations",
    scope="Cluster",
    short_names=("odintegration",),
)
class Integration(Resource):
    """Cluster-scoped record of an installed integration."""

    spec: IntegrationSpec = Field(description="Desired configuration of the integration.")
    status: IntegrationStatus | None = Field(
        default=None,
        description="Current observed state of the integration.",
    )
