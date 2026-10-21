"""Redeeming invites into users."""

from datetime import UTC, datetime

from cloudcoil.apimachinery import ObjectMeta
from cloudcoil.controller import get_condition
from cloudcoil.errors import ResourceConflict

from lib_opendefence_core.logging import get_logger
from lib_opendefence_core.models.v1alpha1 import (
    API_VERSION,
    REFERENCES_RESOLVED_CONDITION,
    Invite,
    InviteSpec,
    InviteStatus,
    User,
    UserSpec,
)
from opendefence_core.api.lib.codes import generate_code
from opendefence_core.api.lib.users import check_callsign

APPROVAL_CODE_LENGTH = 8
INVITE_CODE_LENGTH = 8
UNLIMITED = -1

logger = get_logger(__name__)


class InviteNotRedeemable(Exception):
    """No invite with the code, or it is not ready, expired or used up"""


async def find_invite(code: str) -> Invite | None:
    """Invite with the code, if it can still be redeemed."""
    async for invite in await Invite.async_list():
        if invite.spec.code == code and _is_redeemable(invite):
            return invite
    return None


async def list_invites() -> list[Invite]:
    """Invites an administrator can manage, auto-approving ones excluded."""
    return [invite async for invite in await Invite.async_list() if not invite.spec.auto_approve]


async def unique_invite_code() -> str:
    """Generated code that no invite holds yet."""
    taken = {invite.spec.code async for invite in await Invite.async_list()}
    while (code := generate_code(INVITE_CODE_LENGTH)) in taken:
        pass
    return code


async def create_invite(spec: InviteSpec) -> Invite:
    """Create an invite under a generated name."""
    invite = Invite(
        api_version=API_VERSION,
        kind="Invite",
        metadata=ObjectMeta(generate_name="invite-"),
        spec=spec,
    )
    created = await invite.async_create()
    logger.audit("Invite %s created", created.name)
    return created


async def update_invite(invite: Invite, spec: InviteSpec) -> Invite:
    """Replace the invite spec, failing on a concurrent change."""
    invite.spec = spec
    return await invite.async_update()


async def delete_invite(invite: Invite) -> None:
    """Delete the invite."""
    await invite.async_remove()
    logger.audit("Invite %s deleted", invite.name)


async def redeem(code: str, callsign: str) -> User:
    """Create a user from the invite code, using one use of the invite."""
    invite = await find_invite(code)
    if invite is None:
        raise InviteNotRedeemable
    user = _new_user(invite, callsign)
    await check_callsign(callsign)
    await _use(invite)
    created = await user.async_create()
    logger.audit("Invite %s redeemed as user %s", invite.name, created.name)
    return created


def _used(invite: Invite) -> int:
    return invite.status.used if invite.status else 0


def _is_ready(invite: Invite) -> bool:
    ready = get_condition(invite, REFERENCES_RESOLVED_CONDITION)
    return ready is not None and ready.status == "True"


def _is_redeemable(invite: Invite) -> bool:
    expired = invite.spec.valid_until is not None and invite.spec.valid_until <= datetime.now(UTC)
    used_up = invite.spec.use_count != UNLIMITED and _used(invite) >= invite.spec.use_count
    return _is_ready(invite) and not expired and not used_up


def _new_user(invite: Invite, callsign: str) -> User:
    return User(
        api_version=API_VERSION,
        kind="User",
        metadata=ObjectMeta(generate_name="user-"),
        spec=UserSpec(
            callsign=callsign,
            role_refs=invite.spec.role_refs,
            group_refs=invite.spec.group_refs,
            approval_code=generate_code(APPROVAL_CODE_LENGTH),
            approved_at=datetime.now(UTC) if invite.spec.auto_approve else None,
        ),
    )


async def _use(invite: Invite) -> None:
    invite.status = invite.status or InviteStatus()
    invite.status.used += 1
    try:
        await invite.async_update_status()
    except ResourceConflict as exc:
        raise InviteNotRedeemable from exc  # Invite changed since it was read
