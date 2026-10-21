"""Reading installed integrations."""

from lib_opendefence_core.models.v1alpha1 import Integration


async def list_integrations() -> list[Integration]:
    """Every installed integration."""
    return [integration async for integration in await Integration.async_list()]
