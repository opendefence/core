"""Redeeming invites into users."""

from datetime import UTC, datetime
from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import get_condition
from cloudcoil.errors import ResourceConflict

from opendefence_core.api.lib.common.codes import generate_code
from opendefence_core.k8s_operator.models.v1alpha1.common import API_VERSION
from opendefence_core.k8s_operator.models.v1alpha1.invite import Invite, InviteStatus
from opendefence_core.k8s_operator.models.v1alpha1.user import User, UserSpec

APPROVAL_CODE_LENGTH = 8
UNLIMITED = -1


class InviteNotRedeemable(Exception):
    """No invite with the code, or it is not ready, expired or used up"""


class CallsignTaken(Exception):
    """A user with the callsign already exists"""


async def find_invite(code: str) -> Invite | None:
    """Invite with the code, if it can still be redeemed."""
    # TODO: A better way to do this?
    async for invite in await Invite.async_list():
        if invite.spec.code == code and _is_redeemable(invite):
            return invite
    return None


async def redeem(code: str, callsign: str) -> User:
    """Create a user from the invite code, using one use of the invite."""
    invite = await find_invite(code)
    if invite is None:
        raise InviteNotRedeemable
    user = _new_user(invite, callsign)
    await _check_callsign(user)
    await _use(invite)
    return await user.async_create()


def _used(invite: Invite) -> int:
    return invite.status.used if invite.status else 0


def _is_ready(invite: Invite) -> bool:
    ready = get_condition(invite, "ReferencesResolved")
    return ready is not None and ready.status == "True"


def _is_redeemable(invite: Invite) -> bool:
    expired = invite.spec.valid_until is not None and invite.spec.valid_until <= datetime.now(UTC)
    used_up = invite.spec.use_count != UNLIMITED and _used(invite) >= invite.spec.use_count
    return _is_ready(invite) and not expired and not used_up


def _new_user(invite: Invite, callsign: str) -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(name=callsign),
        spec=UserSpec(
            callsign=callsign,
            role_refs=invite.spec.role_refs,
            group_refs=invite.spec.group_refs,
            approval_code=generate_code(APPROVAL_CODE_LENGTH),
            approved_at=datetime.now(UTC) if invite.spec.auto_approve else None,
        ),
    )


async def _check_callsign(user: User) -> None:
    """Fail on a taken callsign before the invite is used."""
    try:
        await user.async_create(dry_run=True)
    except ResourceConflict as exc:
        raise CallsignTaken from exc


async def _use(invite: Invite) -> None:
    invite.status = invite.status or InviteStatus()
    invite.status.used += 1
    try:
        await invite.async_update_status()
    except ResourceConflict as exc:
        raise InviteNotRedeemable from exc  # Invite changed since it was read
