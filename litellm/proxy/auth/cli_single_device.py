"""Keep only a user's latest CLI login alive when an operator flags them for it.

An operator sets ``cli_single_device: true`` in a user's metadata. Every CLI login (``lite login``,
``lite login --pkce``, the Claude Code login) gets a fresh login id stamped into the credential's own
metadata, and for a flagged user the newest id is written to the user's metadata. A credential whose id is
not the user's current one is refused, so logging in on a new device signs the old one out.

A refresh is not a login: the proxy-API refresh token's rotation chain (``family``) is the login id, so a
renewal re-mints the credential with the id it already had and the device stays signed in. A flagged user
with no recorded id yet keeps every credential they hold until their first login after the flag is set.
Design notes: ``CLI_SINGLE_DEVICE_DESIGN.md``.
"""

import json
import secrets
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Final, Protocol

from fastapi import status

from litellm._logging import verbose_proxy_logger
from litellm.proxy._types import LiteLLM_UserTable, ProxyErrorTypes, ProxyException, UserAPIKeyAuth

if TYPE_CHECKING:
    from litellm.proxy.common_utils.user_api_key_cache import UserApiKeyCache
    from litellm.proxy.utils import PrismaClient

SINGLE_DEVICE_FLAG: Final = "cli_single_device"
"""User metadata key an operator sets to ``true`` to keep that user to one CLI device."""

ACTIVE_LOGIN_KEY: Final = "cli_active_login_id"
"""User metadata key holding the login id of the user's latest CLI login."""

TOKEN_LOGIN_KEY: Final = "cli_login_id"
"""Credential metadata key holding the login id the credential was minted for."""

SIGNED_OUT_MESSAGE: Final = "다른 기기에서 로그인해 이 기기의 로그인이 끝났습니다. `lite login` 을 다시 하세요"

ReloadUser = Callable[[str], Awaitable[LiteLLM_UserTable | None]]


class UserRows(Protocol):
    async def find_by_id(self, id_value: str, id_field: str = "id") -> LiteLLM_UserTable | None: ...

    async def update(
        self, id_value: str, data: Mapping[str, object], id_field: str = "id"
    ) -> LiteLLM_UserTable | None: ...


def new_cli_login_id() -> str:
    return secrets.token_urlsafe(16)


def cli_login_metadata(login_id: str | None) -> dict[str, object]:
    """The credential metadata that carries ``login_id``; empty for a credential minted outside a CLI login."""
    return {} if login_id is None else {TOKEN_LOGIN_KEY: login_id}


def _single_device(user_metadata: Mapping[str, object] | None) -> bool:
    return user_metadata is not None and user_metadata.get(SINGLE_DEVICE_FLAG) is True


def is_signed_out(token_metadata: Mapping[str, object] | None, user_metadata: Mapping[str, object] | None) -> bool:
    """True when a flagged user's latest login is not the one this credential was minted for."""
    if not _single_device(user_metadata) or user_metadata is None:
        return False
    active: Final = user_metadata.get(ACTIVE_LOGIN_KEY)
    if not isinstance(active, str):
        return False
    minted_for: Final = None if token_metadata is None else token_metadata.get(TOKEN_LOGIN_KEY)
    return minted_for != active


async def enforce_cli_single_device(token: UserAPIKeyAuth, user: LiteLLM_UserTable, reload_user: ReloadUser) -> None:
    """Refuse ``token`` with a 401 when its user has logged in on another device since it was minted.

    The cached user row can be older than a login this very device just made, so a mismatch is re-checked
    against a fresh read before refusing. The message names no credential.
    """
    if not is_signed_out(token.metadata, user.metadata):
        return
    fresh: Final = await reload_user(user.user_id)
    if fresh is not None and not is_signed_out(token.metadata, fresh.metadata):
        return
    raise ProxyException(
        message=SIGNED_OUT_MESSAGE,
        type=ProxyErrorTypes.auth_error,
        param=None,
        code=status.HTTP_401_UNAUTHORIZED,
    )


def db_user_reloader(prisma_client: "PrismaClient", cache: "UserApiKeyCache") -> ReloadUser:
    """Reads the user row straight from the database, past the cache, for ``enforce_cli_single_device``."""
    from litellm.proxy.auth.auth_checks import get_user_object  # noqa: PLC0415  # auth_checks imports this module

    async def reload(user_id: str) -> LiteLLM_UserTable | None:
        return await get_user_object(user_id, prisma_client, cache, user_id_upsert=False, check_db_only=True)

    return reload


async def record_cli_login(users: UserRows, user_id: str, login_id: str) -> None:
    """Make ``login_id`` the only live CLI login of a flagged user; leave every other user untouched.

    A database fault never fails the login itself: the new device signs in, and the user's other devices
    stay signed in until a later login is recorded.
    """
    try:
        user: Final = await users.find_by_id(user_id, id_field="user_id")
        if user is None or not _single_device(user.metadata):
            return
        metadata: Final = {**(user.metadata or {}), ACTIVE_LOGIN_KEY: login_id}
        await users.update(user_id, {"metadata": json.dumps(metadata)}, id_field="user_id")
    except Exception as e:  # noqa: BLE001  # the login already succeeded; only the single-device record is lost
        verbose_proxy_logger.warning("Could not record the CLI login for user %s: %s", user_id, e)


async def record_cli_login_in_db(user_id: str, login_id: str) -> None:
    """``record_cli_login`` against the proxy's database, read from the writer so the flag is current."""
    from litellm.proxy.proxy_server import prisma_client  # noqa: PLC0415  # rebound after startup, so read it per call
    from litellm.repositories.user_repository import UserRepository  # noqa: PLC0415  # keeps auth imports light

    if prisma_client is None:
        return
    await record_cli_login(UserRepository(prisma_client, use_writer=True), user_id, login_id)
