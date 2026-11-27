"""Integration custom resource."""

from typing import Annotated, Literal

from cloudcoil.crd import ListType, PrinterColumn, custom_resource
from cloudcoil.pydantic import BaseModel
from cloudcoil.resources import Resource
from pydantic import Field

from lib_opendefence_core.models.v1alpha1.common import API_VERSION, PlatformStatus

# An extra role's name becomes Role metadata.name
ROLE_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
# Route paths go into Traefik rules, so only unreserved URL path characters are allowed
ROUTE_PATH_PATTERN = r"^/[A-Za-z0-9._~/-]*$"
# A route matches a plain path, or a regular expression that starts with ^/ and holds no backtick
ROUTE_MATCH_PATTERN = r"^(/[A-Za-z0-9._~/-]*|\^/[^`\s]*)$"
# Condition an Integration reports once its listed ports are open
PORTS_READY_CONDITION = "PortsReady"


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


class ProductModuleFederation(BaseModel):
    """A module federation remote that the platform UI loads."""

    remote_entry: str = Field(
        min_length=1,
        alias="remoteEntry",
        description="URL of the remote entry, such as /integrations/<name>/ui/remoteEntry.js.",
    )


class ProductUrl(BaseModel):
    """A URL that the platform UI opens or fetches."""

    url: str = Field(
        min_length=1,
        description="URL of the link or the markdown document.",
    )


class ProductUi(BaseModel):
    """How the product is opened in the platform UI. Set the member that type names."""

    type: Literal["ModuleFederation", "Link", "Markdown"] = Field(
        description="Which member describes the UI: moduleFederation, link, or markdown.",
    )
    module_federation: ProductModuleFederation | None = Field(
        default=None,
        alias="moduleFederation",
        description="The remote to load when type is ModuleFederation.",
    )
    link: ProductUrl | None = Field(
        default=None,
        description="The link to open when type is Link.",
    )
    markdown: ProductUrl | None = Field(
        default=None,
        description="The markdown document to show when type is Markdown.",
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
    ui: ProductUi | None = Field(
        default=None,
        description="How the product is opened in the platform UI.",
    )
    descriptions: Annotated[list[ProductDescription], ListType("map", keys=("language",))] = Field(
        default_factory=list,
        description="Localized titles and descriptions, one entry per language.",
    )


class IntegrationHttpRoute(BaseModel):
    """One HTTP path from outside the cluster to a Service in the integration namespace."""

    host: Literal["App", "Public"] = Field(
        description="App is app.<domain> and needs a client certificate. Public is <domain> and needs none.",
    )
    path: str = Field(
        max_length=256,
        pattern=ROUTE_MATCH_PATTERN,
        description=(
            "Path prefix to serve, or a regular expression that starts with ^ in Traefik PathRegexp syntax. "
            "/integrations/<name> is reserved for the integration."
        ),
    )
    strip_prefix: str | None = Field(
        default=None,
        alias="stripPrefix",
        pattern=ROUTE_PATH_PATTERN,
        description="Prefix removed from the path before the request reaches the Service. Unset keeps the path.",
    )
    blocked_paths: list[
        Annotated[str, Field(pattern=ROUTE_PATH_PATTERN, description="Path that the platform refuses to serve.")]
    ] = Field(
        default_factory=list,
        alias="blockedPaths",
        description="Paths below this route that the platform refuses to serve.",
    )
    service: str = Field(
        min_length=1,
        max_length=63,
        description="Name of the Service in the integration namespace.",
    )
    port: int = Field(
        ge=1,
        le=65535,
        description="Port of the Service.",
    )


class IntegrationPort(BaseModel):
    """One TCP or UDP port from outside the cluster to a Service in the integration namespace."""

    name: str = Field(
        min_length=1,
        max_length=63,
        description="Name of this port, unique in the integration.",
    )
    protocol: Literal["TCP", "UDP"] = Field(
        description="Transport protocol of the port.",
    )
    public_port: int | None = Field(
        default=None,
        alias="publicPort",
        ge=1024,
        le=65535,
        description="Port that clients connect to. Core assigns one from its pool when this is unset.",
    )
    service: str = Field(
        min_length=1,
        max_length=54,
        description="Name of the Service in the integration namespace.",
    )
    port: int = Field(
        ge=1,
        le=65535,
        description="Port of the Service.",
    )


class IntegrationIngress(BaseModel):
    """Traffic from outside the cluster."""

    http_routes: Annotated[list[IntegrationHttpRoute], ListType("map", keys=("host", "path"))] = Field(
        default_factory=list,
        alias="httpRoutes",
        description="HTTP paths to serve.",
    )
    ports: Annotated[list[IntegrationPort], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="TCP and UDP ports to open.",
    )


class IntegrationNetwork(BaseModel):
    """Network access the integration needs from the platform."""

    ingress: IntegrationIngress = Field(
        default_factory=IntegrationIngress,
        description="Traffic from outside the cluster.",
    )


class IntegrationSpec(BaseModel):
    """Desired identity, product info, roles, and network access of an integration."""

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
    network: IntegrationNetwork = Field(
        default_factory=IntegrationNetwork,
        description="Network access the integration needs.",
    )


class IntegrationPortStatus(BaseModel):
    """Public port of one listed port."""

    name: str = Field(description="Name of the port in the spec.")
    protocol: Literal["TCP", "UDP"] = Field(description="Transport protocol of the port.")
    public_port: int = Field(alias="publicPort", description="Port that clients connect to.")


class IntegrationStatus(PlatformStatus):
    """Ready conditions and public ports of an integration. Integrations have no outgoing references."""

    ports: Annotated[list[IntegrationPortStatus], ListType("map", keys=("name",))] = Field(
        default_factory=list,
        description="Public port of each listed port, assigned or pinned.",
    )


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
