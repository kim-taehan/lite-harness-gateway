from datetime import UTC, datetime

import pytest

from litellm.caching.caching import DualCache
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.common_utils.proxy_rate_limit_error import ProxyRateLimitError
from litellm.proxy.hooks.daily_token_limiter import PROXY_DailyTokenLimiter
from litellm.proxy.utils import InternalUsageCache

MORNING = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
LATE_NIGHT = datetime(2026, 11, 5, 23, 59, 30, tzinfo=UTC)
NEXT_DAY = datetime(2026, 11, 6, 0, 0, 1, tzinfo=UTC)
TEAM = "team-ex"


def _limiter(cache: DualCache, now: datetime) -> PROXY_DailyTokenLimiter:
    return PROXY_DailyTokenLimiter(internal_usage_cache=InternalUsageCache(cache), clock=lambda: now)


def _caller(**limits) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(api_key="hashed-key-a", team_id=TEAM, user_id="alice", **limits)


async def _use(limiter: PROXY_DailyTokenLimiter, tokens: int, key="hashed-key-a", team=TEAM, user="alice") -> None:
    await limiter.async_log_success_event(
        kwargs={
            "standard_logging_object": {
                "total_tokens": tokens,
                "metadata": {"user_api_key_hash": key, "user_api_key_team_id": team, "user_api_key_user_id": user},
            }
        },
        response_obj=None,
        start_time=None,
        end_time=None,
    )


async def _check(limiter: PROXY_DailyTokenLimiter, caller: UserAPIKeyAuth, call_type="acompletion") -> object:
    return await limiter.async_pre_call_hook(
        user_api_key_dict=caller, cache=DualCache(), data={"model": "m"}, call_type=call_type
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "limit_field", ["tpd_limit", "team_tpd_limit", "team_member_tpd_limit"], ids=["key", "team", "team-member"]
)
async def test_calls_pass_until_the_day_total_reaches_the_limit(limit_field):
    limiter = _limiter(DualCache(), MORNING)
    caller = _caller(**{limit_field: 1000})

    await _use(limiter, 999)
    assert await _check(limiter, caller) is None

    await _use(limiter, 1)
    with pytest.raises(ProxyRateLimitError) as raised:
        await _check(limiter, caller)
    assert raised.value.status_code == 429
    assert "1000 of 1000" in raised.value.message


@pytest.mark.asyncio
async def test_rejection_tells_the_client_to_retry_at_utc_midnight():
    limiter = _limiter(DualCache(), LATE_NIGHT)
    await _use(limiter, 10)

    with pytest.raises(ProxyRateLimitError) as raised:
        await _check(limiter, _caller(tpd_limit=10))
    assert raised.value.headers["retry-after"] == "30"


@pytest.mark.asyncio
async def test_usage_resets_on_the_next_utc_day():
    cache = DualCache()
    await _use(_limiter(cache, LATE_NIGHT), 5000)

    assert await _check(_limiter(cache, NEXT_DAY), _caller(tpd_limit=1000)) is None


@pytest.mark.asyncio
async def test_team_limit_is_shared_by_every_key_in_the_team():
    limiter = _limiter(DualCache(), MORNING)
    await _use(limiter, 600, key="hashed-key-a", user="alice")
    await _use(limiter, 400, key="hashed-key-b", user="bob")

    with pytest.raises(ProxyRateLimitError):
        await _check(
            limiter, UserAPIKeyAuth(api_key="hashed-key-c", team_id=TEAM, user_id="carol", team_tpd_limit=1000)
        )


@pytest.mark.asyncio
async def test_member_limit_counts_each_member_separately():
    limiter = _limiter(DualCache(), MORNING)
    await _use(limiter, 1000, key="hashed-key-a", user="alice")

    with pytest.raises(ProxyRateLimitError):
        await _check(limiter, _caller(team_member_tpd_limit=1000))
    assert (
        await _check(
            limiter, UserAPIKeyAuth(api_key="hashed-key-b", team_id=TEAM, user_id="bob", team_member_tpd_limit=1000)
        )
        is None
    )


@pytest.mark.asyncio
async def test_member_of_another_team_is_not_charged_for_this_team():
    limiter = _limiter(DualCache(), MORNING)
    await _use(limiter, 1000, key="hashed-key-a", team="team-platform", user="alice")

    assert await _check(limiter, _caller(team_member_tpd_limit=1000, team_tpd_limit=1000)) is None


@pytest.mark.asyncio
async def test_batch_submissions_are_left_to_the_batch_limiter():
    limiter = _limiter(DualCache(), MORNING)
    await _use(limiter, 5000)

    assert await _check(limiter, _caller(tpd_limit=1000), call_type="acreate_batch") is None


@pytest.mark.asyncio
async def test_unlimited_caller_is_never_rejected():
    limiter = _limiter(DualCache(), MORNING)
    await _use(limiter, 10_000_000)

    assert await _check(limiter, _caller()) is None
