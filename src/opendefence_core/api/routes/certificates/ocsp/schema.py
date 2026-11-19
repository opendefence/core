"""Response schema for the OCSP routes."""

from typing import Any

OCSP_RESPONSE_MEDIA_TYPE = "application/ocsp-response"

OCSP_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {OCSP_RESPONSE_MEDIA_TYPE: {}},
        "description": "DER OCSPResponse. OCSP errors, such as malformedRequest, also use 200.",
    },
}
