"""Certificate endpoints: the caller sends a CSR and downloads the issued chain."""

import base64

from cloudcoil.controller import get_condition
from cloudcoil.errors import APIError, ResourceNotFound
from cloudcoil.models.cert_manager.v1 import CertificateRequest
from cloudcoil.patches import diff
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from lib_opendefence_core.models.v1alpha1 import CERTIFICATE_READY_CONDITION
from opendefence_core.api.dependencies import JWTUser
from opendefence_core.api.routes.certificates.schema import CSR_RESPONSES, PEM_MEDIA_TYPE, PEM_RESPONSES, CsrRequest
from opendefence_core.certificates import approval_used, certificate_identity, check_csr, wants_certificate
from opendefence_core.naming import PUBLIC_CERT_NAMESPACE, user_certificate_name

router = APIRouter(prefix="/certificates", tags=["certificates"])

CERTIFICATE_NOT_ISSUED_MESSAGE = "Certificate not issued yet."


@router.post("/csr", status_code=status.HTTP_202_ACCEPTED, responses=CSR_RESPONSES)
async def submit_csr(request: CsrRequest, user: JWTUser) -> None:
    """Store the caller's CSR for the operator to sign under the current approval."""
    if not wants_certificate(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User is not approved.")
    if approval_used(user):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Approval already used.")
    try:
        check_csr(request.csr.encode(), *certificate_identity(user))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    desired = user.model_copy(deep=True)
    desired.spec.certificate_signing_request = request.csr
    try:
        await user.async_patch(diff(user, desired))
    except APIError as exc:
        if exc.status_code not in (409, 422):
            raise
        raise HTTPException(status.HTTP_409_CONFLICT, detail="User changed; retry.") from exc


@router.get("/chain.pem", response_class=Response, responses=PEM_RESPONSES)
async def get_certificate(user: JWTUser) -> Response:
    """Download the caller's issued certificate chain once the operator has accepted it."""
    ready = get_condition(user, CERTIFICATE_READY_CONDITION)
    if not wants_certificate(user) or ready is None or ready.status != "True":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=CERTIFICATE_NOT_ISSUED_MESSAGE)
    try:
        issued = await CertificateRequest.async_get(user_certificate_name(user), PUBLIC_CERT_NAMESPACE)
    except ResourceNotFound as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=CERTIFICATE_NOT_ISSUED_MESSAGE) from exc
    if issued.status is None or not issued.status.certificate:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=CERTIFICATE_NOT_ISSUED_MESSAGE)
    chain = base64.b64decode(issued.status.certificate) + base64.b64decode(issued.status.ca or "")
    return Response(content=chain, media_type=PEM_MEDIA_TYPE)
