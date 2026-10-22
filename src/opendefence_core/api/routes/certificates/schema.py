"""Request and response schemas for the certificates routes."""

from typing import Any

from pydantic import Field

from opendefence_core.api.schema import ApiModel, ErrorResponse

PEM_MEDIA_TYPE = "application/x-pem-file"


class CsrRequest(ApiModel):
    """PEM PKCS#10 request for the identity in the caller's enrollment status."""

    csr: str = Field(max_length=8192)


CSR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Request does not match the certificate identity."},
    401: {"model": ErrorResponse, "description": "Not authenticated."},
    403: {"model": ErrorResponse, "description": "User not approved."},
    409: {"model": ErrorResponse, "description": "Approval already used; a fresh approval is required."},
}

PEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {PEM_MEDIA_TYPE: {}}, "description": "Certificate chain, leaf first."},
    401: {"model": ErrorResponse, "description": "Not authenticated."},
    409: {"model": ErrorResponse, "description": "Certificate not issued yet."},
}
