"""The proxy-API grant tail treats a fresh grant as a CLI login and a refresh as the same login."""

import json
from collections.abc import Iterator, Sequence
from typing import Final
from unittest.mock import patch

import pytest
from fastapi import Response

from litellm.caching.dual_cache import DualCache
from litellm.proxy._experimental.mcp_server.gateway_dcr_flow import (
    PROXY_API_AUDIENCE,
    MintedProxyCredential,
    ProxyCredentialMintFailure,
    SessionSigning,
    _ProxyCredentialIssuer,  # pyright: ignore[reportPrivateUsage]  # the grant tail every proxy-API grant shares
    _SingleUseGuard,  # pyright: ignore[reportPrivateUsage]  # the grant tail every proxy-API grant shares
    resolve_session_signing,
)
from litellm.proxy._experimental.mcp_server.outbound_credentials.session_credentials import (
    SessionRefreshOpened,
    open_session_refresh_bearer,
)
from litellm.proxy._experimental.mcp_server.outbound_credentials.session_token import SessionPrincipal
from litellm.proxy._types import LiteLLM_UserTable
from litellm.proxy.auth.cli_single_device import ACTIVE_LOGIN_KEY, SINGLE_DEVICE_FLAG
from tests.unit.proxy.auth.cli_user_table_fake import FakePrisma

_USER_ID: Final = "user-123"
_CLIENT_ID: Final = "native-cli"
_PRINCIPAL: Final = SessionPrincipal(user_id=_USER_ID, client_id=_CLIENT_ID, audience=PROXY_API_AUDIENCE)


class _LoginMinter:
    def __init__(self) -> None:
        self.login_ids: tuple[str | None, ...] = ()

    async def __call__(
        self,
        user_id: str,
        team_id: str | None,
        /,
        *,
        allowed_routes: Sequence[str] | None = None,
        cli_login_id: str | None = None,
    ) -> MintedProxyCredential | ProxyCredentialMintFailure:
        self.login_ids = (*self.login_ids, cli_login_id)
        return MintedProxyCredential(key=f"cli-{cli_login_id}", expires_in=3600, user_id=user_id, team_id=team_id)


@pytest.fixture
def prisma() -> Iterator[FakePrisma]:
    flagged: Final = FakePrisma(
        LiteLLM_UserTable(user_id=_USER_ID, user_role="internal_user", models=[], metadata={SINGLE_DEVICE_FLAG: True})
    )
    with patch(  # test-quality-ok: the login record reads this proxy_server module global and has no injection seam
        "litellm.proxy.proxy_server.prisma_client", flagged
    ):
        yield flagged


def _signing() -> SessionSigning:
    signing: Final = resolve_session_signing("sk-master-key-for-single-device", "test")
    assert isinstance(signing, SessionSigning)
    return signing


def _refresh_family(response: Response, signing: SessionSigning) -> str:
    opened: Final = open_session_refresh_bearer(
        json.loads(bytes(response.body))["refresh_token"], signing.keys, signing.now, expected_client_id=_CLIENT_ID
    )
    assert isinstance(opened, SessionRefreshOpened)
    return opened.family


def _active_login(prisma: FakePrisma) -> object:
    assert prisma.table.row is not None
    assert prisma.table.row.metadata is not None
    return prisma.table.row.metadata.get(ACTIVE_LOGIN_KEY)


@pytest.mark.asyncio
async def test_a_fresh_grant_is_a_new_login_that_its_refresh_chain_carries(prisma: FakePrisma) -> None:
    signing: Final = _signing()
    minter: Final = _LoginMinter()
    issue: Final = _ProxyCredentialIssuer(signing, minter, _SingleUseGuard(DualCache()))

    granted: Final = await issue(_PRINCIPAL, claim_key="code-1", claim_ttl_seconds=60, replayed="used")
    login_id: Final = minter.login_ids[0]
    assert granted.status_code == 200
    assert login_id is not None
    assert _refresh_family(granted, signing) == login_id
    assert _active_login(prisma) == login_id

    refreshed: Final = await issue(
        _PRINCIPAL, claim_key="refresh-1", claim_ttl_seconds=60, replayed="used", family=login_id
    )
    assert refreshed.status_code == 200
    assert minter.login_ids[1] == login_id
    assert _refresh_family(refreshed, signing) == login_id
    assert _active_login(prisma) == login_id


@pytest.mark.asyncio
async def test_a_replayed_grant_does_not_sign_out_the_device_that_redeemed_it(prisma: FakePrisma) -> None:
    minter: Final = _LoginMinter()
    issue: Final = _ProxyCredentialIssuer(_signing(), minter, _SingleUseGuard(DualCache()))

    redeemed: Final = await issue(_PRINCIPAL, claim_key="code-1", claim_ttl_seconds=60, replayed="used")
    replayed: Final = await issue(_PRINCIPAL, claim_key="code-1", claim_ttl_seconds=60, replayed="used")

    assert redeemed.status_code == 200
    assert replayed.status_code == 400
    assert _active_login(prisma) == minter.login_ids[0]
