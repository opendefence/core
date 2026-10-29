"""Health response bodies."""

from opendefence_core.api.schema import ApiModel


class HealthResponse(ApiModel):
    """The deployment that answered."""

    status: str
    deployment: str
    domain: str
