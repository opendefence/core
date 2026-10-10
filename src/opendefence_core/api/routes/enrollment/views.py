"""Enrollment endpoints."""

from fastapi import APIRouter, HTTPException, status

from opendefence_core.api.lib.common.invites import CallsignTaken, InviteNotRedeemable, find_invite, redeem
from opendefence_core.api.lib.common.jwt import issue
from opendefence_core.api.lib.middleware.jwt import JWTUser
from opendefence_core.api.routes.enrollment.schema import (
    CheckRequest,
    CheckResponse,
    EnrollmentStatus,
    EnrollRequest,
    EnrollResponse,
)

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@router.post("/check")
async def check(request: CheckRequest) -> CheckResponse:
    """Check an invite code before asking for a callsign.

    Nothing is reserved, so another user may take the last use before this one creates their user.
    """
    return CheckResponse(valid=await find_invite(request.code) is not None)


@router.post("", status_code=status.HTTP_201_CREATED)
async def enroll(request: EnrollRequest) -> EnrollResponse:
    """Redeem an invite code as a new user."""
    try:
        user = await redeem(request.code, request.callsign)
    except InviteNotRedeemable as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from exc
    except CallsignTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT) from exc
    return EnrollResponse(status=EnrollmentStatus.from_resource(user), token=issue(user))


@router.get("")
async def enrollment_status(user: JWTUser) -> EnrollmentStatus:
    """Enrollment status of the calling user, polled while waiting for approval."""
    return EnrollmentStatus.from_resource(user)
