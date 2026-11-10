"""``lite login`` counts as a CLI login for single-device users."""

from typing import Final
from unittest.mock import patch

import pytest

from litellm.caching.dual_cache import DualCache
from litellm.proxy._types import LiteLLM_UserTable
from litellm.proxy.auth.auth_checks import ExperimentalUIJWTToken
from litellm.proxy.auth.cli_single_device import ACTIVE_LOGIN_KEY, SINGLE_DEVICE_FLAG, TOKEN_LOGIN_KEY
from litellm.proxy.management_endpoints.ui_sso import (
    _get_cli_sso_flow_cache_key,  # pyright: ignore[reportPrivateUsage]  # seeds the completed device flow
    _hash_cli_sso_secret,  # pyright: ignore[reportPrivateUsage]  # seeds the completed device flow
    cli_poll_key,
)
from tests.unit.proxy.auth.cli_user_table_fake import FakePrisma

_USER_ID: Final = "cli-user"
_POLL_SECRET: Final = "poll-secret"


def _completed_flow(cache: DualCache, key_id: str) -> None:
    cache.set_cache(
        key=_get_cli_sso_flow_cache_key(key_id),
        value={
            "poll_secret_hash": _hash_cli_sso_secret(_POLL_SECRET),
            "sso_complete": True,
            "user_code_verified": True,
            "session_data": {"user_id": _USER_ID, "user_role": "internal_user", "teams": [], "models": []},
        },
        ttl=600,
    )


async def _lite_login(cache: DualCache, key_id: str) -> object:
    _completed_flow(cache, key_id)
    response: Final = await cli_poll_key(key_id=key_id, team_id=None, x_litellm_cli_poll_secret=_POLL_SECRET)
    token: Final = ExperimentalUIJWTToken.get_key_object_from_ui_hash_key(response["key"])
    assert token is not None
    return token.metadata[TOKEN_LOGIN_KEY]


@pytest.mark.asyncio
async def test_each_lite_login_becomes_the_flagged_users_only_live_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-salt-single-device-test")
    cache: Final = DualCache()
    prisma: Final = FakePrisma(
        LiteLLM_UserTable(user_id=_USER_ID, user_role="internal_user", models=[], metadata={SINGLE_DEVICE_FLAG: True})
    )
    with (
        patch(  # test-quality-ok: the poll reads this proxy_server module global and has no injection seam
            "litellm.proxy.proxy_server.cli_sso_session_cache", cache
        ),
        patch(  # test-quality-ok: the login record reads this proxy_server module global and has no injection seam
            "litellm.proxy.proxy_server.prisma_client", prisma
        ),
    ):
        laptop: Final = await _lite_login(cache, "cli-laptop-login-0001")
        assert prisma.table.row is not None
        assert prisma.table.row.metadata == {SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: laptop}

        desktop: Final = await _lite_login(cache, "cli-desktop-login-0001")

    assert desktop != laptop
    assert prisma.table.row is not None
    assert prisma.table.row.metadata[ACTIVE_LOGIN_KEY] == desktop
