"""Integration response bodies."""

from typing import Self

from lib_opendefence_core.models.v1alpha1 import Integration
from lib_opendefence_core.models.v1alpha1.integration import ProductDescription as SpecDescription
from lib_opendefence_core.models.v1alpha1.integration import ProductInfo, ProductUi
from opendefence_core.api.lib.reconciliation import ReconciliationState, state_of
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
    version: str
    state: ReconciliationState
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
        return cls(
            id=id_of(integration),
            name=integration.name or "",
            version=integration.spec.version,
            state=state_of(integration.status, integration.metadata.generation if integration.metadata else None),
            title=described.title if described else integration.spec.display_name,
            description=described.description if described else "",
            language=described.language if described else language,
            icon=info.icon if info else None,
            docs=info.docs if info else None,
            component=_component(info.ui if info else None),
        )


def _component(ui: ProductUi | None) -> ProductComponent | None:
    """The UI's type and ref, or None when the member that the type names is unset."""
    if ui is None:
        return None
    kind, ref = {
        "ModuleFederation": ("component", ui.module_federation.remote_entry if ui.module_federation else None),
        "Link": ("link", ui.link.url if ui.link else None),
        "Markdown": ("markdown", ui.markdown.url if ui.markdown else None),
    }[ui.type]
    return ProductComponent(type=kind, ref=ref) if ref else None


def _description(info: ProductInfo | None, language: str) -> SpecDescription | None:
    """The requested language, falling back to English, then to whatever is available."""
    described = info.descriptions if info else []
    for wanted in (language, FALLBACK_LANGUAGE):
        for item in described:
            if item.language == wanted:
                return item
    return described[0] if described else None
