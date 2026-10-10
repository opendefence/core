"""Request and response schemas for the certificates routes."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import BaseModel

from opendefence_core.k8s_operator.models.v1alpha1.user import CALLSIGN_PATTERN

PFX_MEDIA_TYPE = "application/x-pkcs12"

Callsign = Annotated[str, Path(pattern=CALLSIGN_PATTERN, description="Callsign of the user.")]


class ErrorResponse(BaseModel):
    """Error body, same shape as FastAPI's HTTPException."""

    detail: str


PFX_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {PFX_MEDIA_TYPE: {}}, "description": "PKCS#12 bundle."},
    401: {"model": ErrorResponse, "description": "Not authenticated."},
    403: {"model": ErrorResponse, "description": "Certificate of another user."},
    409: {"model": ErrorResponse, "description": "Certificate not issued yet."},
}
