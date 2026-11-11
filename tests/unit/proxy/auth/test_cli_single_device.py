from collections.abc import Mapping
from typing import Final

import pytest

from litellm.proxy._types import LiteLLM_UserTable, ProxyException, UserAPIKeyAuth
from litellm.proxy.auth.auth_checks import ExperimentalUIJWTToken
from litellm.proxy.auth.cli_single_device import (
    ACTIVE_LOGIN_KEY,
    SINGLE_DEVICE_FLAG,
    TOKEN_LOGIN_KEY,
    enforce_cli_single_device,
    is_signed_out,
    record_cli_login,
)
from litellm.proxy.auth.user_api_key_auth import (
    _refresh_session_token_grants,  # pyright: ignore[reportPrivateUsage]  # the per-request session check under test
)
from litellm.proxy.common_utils.user_api_key_cache import UserApiKeyCache
from litellm.proxy.utils import ProxyLogging
from litellm.repositories.user_repository import UserRepository
from tests.unit.proxy.auth.cli_user_table_fake import FakePrisma

_USER_ID: Final = "cli-user"


class _BrokenUsers:
    async def find_by_id(self, id_value: str, id_field: str = "id") -> LiteLLM_UserTable | None:
        raise ConnectionError("database unreachable")

    async def update(self, id_value: str, data: Mapping[str, object], id_field: str = "id") -> LiteLLM_UserTable | None:
        raise ConnectionError("database unreachable")


def _user(metadata: Mapping[str, object] | None) -> LiteLLM_UserTable:
    return LiteLLM_UserTable(
        user_id=_USER_ID,
        user_role="internal_user",
        models=[],
        teams=[],
        metadata=None if metadata is None else dict(metadata),
    )


def _session(login_id: str | None) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(
        token="cli-session",
        user_id=_USER_ID,
        is_session_token=True,
        metadata={} if login_id is None else {TOKEN_LOGIN_KEY: login_id},
    )


@pytest.mark.parametrize(
    ("token_login", "user_metadata", "signed_out"),
    [
        ("old", {}, False),
        (None, {}, False),
        ("old", {SINGLE_DEVICE_FLAG: True}, False),
        ("old", {ACTIVE_LOGIN_KEY: "new"}, True),
        ("old", {SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: "new"}, True),
        ("old", {SINGLE_DEVICE_FLAG: "false", ACTIVE_LOGIN_KEY: "new"}, True),
        ("old", {SINGLE_DEVICE_FLAG: None, ACTIVE_LOGIN_KEY: "new"}, True),
        (None, {ACTIVE_LOGIN_KEY: "new"}, True),
        ("new", {ACTIVE_LOGIN_KEY: "new"}, False),
        ("old", {SINGLE_DEVICE_FLAG: False, ACTIVE_LOGIN_KEY: "new"}, False),
    ],
    ids=[
        "before-first-login",
        "before-first-login-old-token",
        "flag-true-before-first-login",
        "older-login-by-default",
        "older-login-flag-true",
        "flag-string-false-is-not-an-exemption",
        "flag-null-is-not-an-exemption",
        "token-minted-before-the-feature",
        "latest-login",
        "exempt",
    ],
)
def test_only_an_exempt_user_keeps_older_logins(
    token_login: str | None, user_metadata: Mapping[str, object], signed_out: bool
) -> None:
    token_metadata: Final = {} if token_login is None else {TOKEN_LOGIN_KEY: token_login}
    assert is_signed_out(token_metadata, user_metadata) is signed_out


@pytest.mark.asyncio
async def test_a_login_becomes_the_users_only_live_one_and_keeps_other_metadata() -> None:
    prisma: Final = FakePrisma(_user({"department": "infra"}))
    users: Final = UserRepository(prisma, use_writer=True)

    await record_cli_login(users, _USER_ID, "laptop")
    await record_cli_login(users, _USER_ID, "desktop")

    assert prisma.table.row is not None
    assert prisma.table.row.metadata == {"department": "infra", ACTIVE_LOGIN_KEY: "desktop"}


@pytest.mark.asyncio
async def test_lifting_an_exemption_keeps_every_device_until_the_next_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-salt-single-device-test")
    prisma: Final = FakePrisma(_user({SINGLE_DEVICE_FLAG: False, ACTIVE_LOGIN_KEY: "laptop", "department": "infra"}))
    desktop: Final = _minted_session("desktop")

    await record_cli_login(UserRepository(prisma, use_writer=True), _USER_ID, "desktop")
    assert prisma.table.row is not None
    assert prisma.table.row.metadata == {SINGLE_DEVICE_FLAG: False, "department": "infra"}

    prisma.table.row = prisma.table.row.model_copy(update={"metadata": {"department": "infra"}})
    assert await _refusal(desktop, prisma) is None
    assert await _refusal(_minted_session("tablet"), prisma) is None


@pytest.mark.parametrize(
    "row", [_user({SINGLE_DEVICE_FLAG: False, "department": "infra"}), None], ids=["exempt", "gone"]
)
@pytest.mark.asyncio
async def test_a_login_is_not_recorded_for_an_exempt_or_missing_user(row: LiteLLM_UserTable | None) -> None:
    prisma: Final = FakePrisma(row)

    await record_cli_login(UserRepository(prisma, use_writer=True), _USER_ID, "laptop")

    assert prisma.table.row == row


@pytest.mark.asyncio
async def test_a_database_fault_while_recording_does_not_fail_the_login() -> None:
    assert await record_cli_login(_BrokenUsers(), _USER_ID, "laptop") is None


@pytest.mark.asyncio
async def test_an_older_login_is_refused_with_a_401_that_names_no_credential() -> None:
    signed_in_elsewhere: Final = _user({SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: "desktop"})

    async def reload(user_id: str) -> LiteLLM_UserTable | None:
        return signed_in_elsewhere

    with pytest.raises(ProxyException) as refused:
        await enforce_cli_single_device(_session("laptop"), signed_in_elsewhere, reload)

    assert refused.value.code == "401"
    assert "lite login" in refused.value.message
    assert "laptop" not in refused.value.message
    assert "cli-session" not in refused.value.message


@pytest.mark.asyncio
async def test_a_mismatch_is_admitted_when_the_user_row_cannot_be_re_read() -> None:
    cached: Final = _user({SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: "laptop"})

    async def reload(user_id: str) -> LiteLLM_UserTable | None:
        raise ConnectionError("database unreachable")

    assert await enforce_cli_single_device(_session("desktop"), cached, reload) is None


@pytest.mark.asyncio
async def test_a_login_newer_than_the_cached_user_row_is_admitted() -> None:
    cached: Final = _user({SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: "laptop"})
    fresh: Final = _user({SINGLE_DEVICE_FLAG: True, ACTIVE_LOGIN_KEY: "desktop"})

    async def reload(user_id: str) -> LiteLLM_UserTable | None:
        return fresh

    assert await enforce_cli_single_device(_session("desktop"), cached, reload) is None


def _minted_session(login_id: str) -> UserAPIKeyAuth:
    blob: Final = ExperimentalUIJWTToken.get_cli_jwt_auth_token(
        user_info=LiteLLM_UserTable(user_id=_USER_ID, user_role="internal_user", models=[]),
        cli_login_id=login_id,
    )
    token: Final = ExperimentalUIJWTToken.get_key_object_from_ui_hash_key(blob)
    assert token is not None
    return token


async def _refusal(token: UserAPIKeyAuth, prisma: FakePrisma) -> str | None:
    """The status code a request with ``token`` is refused with, or None when it is admitted."""
    try:
        await _refresh_session_token_grants(
            valid_token=token,
            prisma_client=prisma,  # pyright: ignore[reportArgumentType]  # in-memory stand-in for the user table
            user_api_key_cache=UserApiKeyCache(),
            parent_otel_span=None,
            proxy_logging_obj=ProxyLogging(user_api_key_cache=UserApiKeyCache()),
        )
    except ProxyException as refused:
        return refused.code
    return None


@pytest.mark.parametrize("metadata", [None, {"department": "infra"}, {SINGLE_DEVICE_FLAG: True}])
@pytest.mark.asyncio
async def test_logging_in_on_a_new_device_signs_the_old_one_out_on_its_next_request(
    monkeypatch: pytest.MonkeyPatch, metadata: Mapping[str, object] | None
) -> None:
    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-salt-single-device-test")
    prisma: Final = FakePrisma(_user(metadata))
    users: Final = UserRepository(prisma, use_writer=True)
    laptop: Final = _minted_session("laptop")
    assert await _refusal(laptop, prisma) is None

    await record_cli_login(users, _USER_ID, "laptop")
    assert await _refusal(laptop, prisma) is None

    desktop: Final = _minted_session("desktop")
    await record_cli_login(users, _USER_ID, "desktop")

    assert await _refusal(desktop, prisma) is None
    assert await _refusal(laptop, prisma) == "401"


@pytest.mark.asyncio
async def test_an_exempt_user_keeps_every_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-salt-single-device-test")
    prisma: Final = FakePrisma(_user({SINGLE_DEVICE_FLAG: False}))
    users: Final = UserRepository(prisma, use_writer=True)
    laptop: Final = _minted_session("laptop")
    await record_cli_login(users, _USER_ID, "laptop")
    desktop: Final = _minted_session("desktop")
    await record_cli_login(users, _USER_ID, "desktop")

    assert await _refusal(laptop, prisma) is None
    assert await _refusal(desktop, prisma) is None
