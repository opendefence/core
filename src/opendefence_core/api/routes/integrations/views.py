"""Integration endpoints."""

from fastapi import APIRouter, Depends

from opendefence_core.api.dependencies import jwt_user
from opendefence_core.api.lib.integrations import list_integrations
from opendefence_core.api.lib.uids import ObjectId
from opendefence_core.api.lookups import integration_or_404
from opendefence_core.api.routes.integrations.schema import FALLBACK_LANGUAGE, IntegrationResponse

router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[Depends(jwt_user)])


@router.get("")
async def read_integrations(language: str = FALLBACK_LANGUAGE) -> list[IntegrationResponse]:
    """Products installed on the platform."""
    integrations = await list_integrations()
    return [IntegrationResponse.from_resource(integration, language) for integration in integrations]


@router.get("/{integration_id}")
async def read_integration(integration_id: ObjectId, language: str = FALLBACK_LANGUAGE) -> IntegrationResponse:
    """Product by id."""
    integration = await integration_or_404(integration_id)
    return IntegrationResponse.from_resource(integration, language)
