"""Integration response bodies."""

from typing import Self

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import ProductDescription as SpecDescription
from lib_opendefence_core.models.v1alpha1.integration import ProductInfo
from opendefence_core.api.lib.uids import id_of
from opendefence_core.api.schema import ApiModel

FALLBACK_LANGUAGE = "en"


class ProductComponent(ApiModel):
    """How the product is opened in the platform UI."""

    type: str
    ref: str


class IntegrationResponse(ApiModel):
    """Installed product, as a card in the platform UI. The name is its package slug."""

    id: str
    name: str
    title: str
    description: str
    language: str
    icon: str | None
    docs: str | None
    component: ProductComponent | None

    @classmethod
    def from_resource(cls, integration: Integration, language: str) -> Self:
        """Response for the Integration resource in the closest language it offers."""
        info = integration.spec.product_info
        described = _description(info, language)
        component = info.component if info else None
        return cls(
            id=id_of(integration),
            name=integration.name or "",
            title=described.title if described else integration.spec.display_name,
            description=described.description if described else "",
            language=described.language if described else language,
            icon=info.icon if info else None,
            docs=info.docs if info else None,
            component=ProductComponent(type=component.type, ref=component.ref) if component else None,
        )


def _description(info: ProductInfo | None, language: str) -> SpecDescription | None:
    """The requested language, falling back to English, then to whatever is available."""
    described = info.descriptions if info else []
    for wanted in (language, FALLBACK_LANGUAGE):
        for item in described:
            if item.language == wanted:
                return item
    return described[0] if described else None
