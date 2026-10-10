"""Certificate download endpoints."""

import asyncio
import base64

from cloudcoil.errors import ResourceNotFound
from cloudcoil.models.kubernetes.core.v1 import Secret
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from opendefence_core.api.config import get_config
from opendefence_core.api.dependencies import JWTUser
from opendefence_core.api.lib.pfx import build_pfx
from opendefence_core.api.routes.certificates.schema import PFX_MEDIA_TYPE, PFX_RESPONSES, Callsign
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, user_secret_name

router = APIRouter(prefix="/certificates", tags=["certificates"])

CERTIFICATE_NOT_ISSUED_MESSAGE = "Certificate not issued yet."
FORBIDDEN_MESSAGE = "Only your own certificate can be downloaded."


@router.get("/{callsign}.pfx", response_class=Response, responses=PFX_RESPONSES)
async def get_user_pfx(callsign: Callsign, user: JWTUser) -> Response:
    """Download the calling user's certificate and private key as a PKCS#12 (.pfx) bundle."""
    if user.name != callsign:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_MESSAGE)
    try:
        secret = await Secret.async_get(user_secret_name(user), PUBLIC_CERT_NAMESPACE)
    except ResourceNotFound as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=CERTIFICATE_NOT_ISSUED_MESSAGE) from exc
    data = secret.data or {}
    if "tls.key" not in data or "tls.crt" not in data:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=CERTIFICATE_NOT_ISSUED_MESSAGE)
    callsign = user.spec.callsign
    pfx = await asyncio.to_thread(
        build_pfx, callsign, base64.b64decode(data["tls.key"]), base64.b64decode(data["tls.crt"])
    )
    filename = f"{callsign}_{get_config().deployment}.pfx"
    return Response(
        content=pfx,
        media_type=PFX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
