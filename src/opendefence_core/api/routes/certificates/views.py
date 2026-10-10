import asyncio
import base64

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from cloudcoil.models.kubernetes.core.v1 import Secret
from cloudcoil.errors import ResourceNotFound

from opendefence_core.api.config import config
from opendefence_core.api.lib.certificates.pfx import build_pfx
from opendefence_core.api.lib.middleware.jwt import JWTUser
from opendefence_core.api.routes.certificates.schema import PFX_MEDIA_TYPE, PFX_RESPONSES, Callsign
from opendefence_core.k8s_operator.controllers._certificates import PUBLIC_CERT_NAMESPACE, secret_name


router = APIRouter(prefix="/certificates", tags=["certificates"])

CERTIFICATE_NOT_ISSUED_MESSAGE = "Certificate not issued yet."
FORBIDDEN_MESSAGE = "Only your own certificate can be downloaded."


@router.get("/{callsign}.pfx", response_class=Response, responses=PFX_RESPONSES)
async def get_user_pfx(
    callsign: Callsign,
    user: JWTUser,
) -> Response:
    """Retrieve user certificate in the form .pfx"""
    if user.name != callsign:
        raise HTTPException(403, detail=FORBIDDEN_MESSAGE)
    try:
        secret = await Secret.async_get(secret_name(user), PUBLIC_CERT_NAMESPACE)
    except ResourceNotFound:
        raise HTTPException(409, detail=CERTIFICATE_NOT_ISSUED_MESSAGE)
    data = secret.data or {}
    if "tls.key" not in data or "tls.crt" not in data:
        raise HTTPException(409, detail=CERTIFICATE_NOT_ISSUED_MESSAGE)
    return Response(
        content=await asyncio.to_thread(
            build_pfx, user.spec.callsign, base64.b64decode(data["tls.key"]), base64.b64decode(data["tls.crt"])
        ),
        media_type=PFX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{user.spec.callsign}_{config.deployment}.pfx"'},
    )
