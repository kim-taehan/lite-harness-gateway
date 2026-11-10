"""The Claude Code login counts as a CLI login for single-device users, and its refresh keeps that login."""

from typing import Final
from unittest.mock import patch

import pytest

from litellm.proxy._experimental.mcp_server.gateway_dcr_flow import (
    MintedProxyCredential,
    ProxyCredentialMintFailure,
)
from litellm.proxy._types import LiteLLM_UserTable
from litellm.proxy.auth.auth_checks import ExperimentalUIJWTToken
from litellm.proxy.auth.cli_single_device import ACTIVE_LOGIN_KEY, SINGLE_DEVICE_FLAG, TOKEN_LOGIN_KEY
from tests.unit.proxy.anthropic_endpoints.test_gateway_endpoints import (
    _complete_flow,  # pyright: ignore[reportPrivateUsage]  # shared device-flow harness
    _gateway_env,  # pyright: ignore[reportPrivateUsage]  # shared device-flow harness
    _refresh,  # pyright: ignore[reportPrivateUsage]  # shared device-flow harness
    _request_token,  # pyright: ignore[reportPrivateUsage]  # shared device-flow harness
    _start_device_flow,  # pyright: ignore[reportPrivateUsage]  # shared device-flow harness
)
from tests.unit.proxy.auth.cli_user_table_fake import FakePrisma

_USER_ID: Final = "user-123"


class _LoginMinter:
    """Mints the real CLI credential, keeping the login id each refresh asked for."""

    def __init__(self) -> None:
        self.login_ids: tuple[str | None, ...] = ()

    async def __call__(
        self, user_id: str, team_id: str | None, *, cli_login_id: str | None = None
    ) -> MintedProxyCredential | ProxyCredentialMintFailure:
        self.login_ids = (*self.login_ids, cli_login_id)
        key: Final = ExperimentalUIJWTToken.get_cli_jwt_auth_token(
            user_info=LiteLLM_UserTable(user_id=user_id, user_role="internal_user", models=[]),
            team_id=team_id,
            cli_login_id=cli_login_id,
        )
        return MintedProxyCredential(key=key, expires_in=7200, user_id=user_id, team_id=team_id)


def _login_id(access_token: str) -> object:
    token: Final = ExperimentalUIJWTToken.get_key_object_from_ui_hash_key(access_token)
    assert token is not None
    return token.metadata[TOKEN_LOGIN_KEY]


def _flagged_user() -> LiteLLM_UserTable:
    return LiteLLM_UserTable(
        user_id=_USER_ID, user_role="internal_user", models=[], teams=["team-a"], metadata={SINGLE_DEVICE_FLAG: True}
    )


def test_each_claude_code_login_becomes_the_users_only_live_login_and_refresh_keeps_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-salt-single-device-test")
    prisma: Final = FakePrisma(_flagged_user())
    minter: Final = _LoginMinter()
    with (
        _gateway_env(minter=minter) as (client, cache),
        patch(  # test-quality-ok: the login record reads this proxy_server module global and has no injection seam
            "litellm.proxy.proxy_server.prisma_client", prisma
        ),
    ):

        def sign_in() -> dict[str, str]:
            device_code: Final = _start_device_flow(client)
            _complete_flow(cache, device_code)
            response: Final = _request_token(client, device_code)
            assert response.status_code == 200
            return response.json()

        laptop: Final = sign_in()
        laptop_login: Final = _login_id(laptop["access_token"])
        assert prisma.table.row is not None
        assert prisma.table.row.metadata == {SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: laptop_login}

        first = _refresh(client, laptop["refresh_token"]).json()
        second = _refresh(client, first["refresh_token"]).json()
        assert _login_id(first["access_token"]) == laptop_login
        assert _login_id(second["access_token"]) == laptop_login
        assert minter.login_ids == (laptop_login, laptop_login)
        assert prisma.table.row.metadata[ACTIVE_LOGIN_KEY] == laptop_login

        desktop: Final = sign_in()

    desktop_login: Final = _login_id(desktop["access_token"])
    assert desktop_login != laptop_login
    assert prisma.table.row is not None
    assert prisma.table.row.metadata[ACTIVE_LOGIN_KEY] == desktop_login
