"""
Daily token limiter for online LLM calls.

Enforces ``tpd_limit`` (tokens per UTC day) on the key, the team, and the
team member. The batch limiter only charges ``tpd_limit`` on batch
submissions, so without this hook a chat completion never counts toward it.

Counters live in the DualCache under one key per scope per UTC day, so the
limit resets at 00:00 UTC. The check runs before the call against tokens
already used, which means the request that crosses the limit still completes
and the next one is rejected.
"""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from litellm import DualCache
from litellm._logging import verbose_proxy_logger
from litellm.caching.redis_cache import log_redis_failure
from litellm.exceptions import RateLimitType
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.common_utils.proxy_rate_limit_error import ProxyRateLimitError
from litellm.proxy.hooks.rate_limiter_utils import resolve_llm_provider_for_rate_limit

if TYPE_CHECKING:
    from litellm.proxy.utils import InternalUsageCache

_BATCH_CALL_TYPES: Final = frozenset({"acreate_batch", "create_batch"})
_COUNTER_TTL_SLACK: Final = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class DailyTokenScope:
    name: str
    value: str
    limit: int


class _LoggedMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    user_api_key_hash: str | None = None
    user_api_key_team_id: str | None = None
    user_api_key_user_id: str | None = None


class _LoggedCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    total_tokens: int = 0
    metadata: _LoggedMetadata = _LoggedMetadata()


def _scope_value(name: str, team_id: str | None, user_id: str | None, api_key: str | None) -> str | None:
    match name:
        case "api_key":
            return api_key
        case "team":
            return team_id
        case "team_member":
            return f"{team_id}:{user_id}" if team_id and user_id else None
        case _:
            return None


def limited_scopes(user_api_key_dict: UserAPIKeyAuth) -> tuple[DailyTokenScope, ...]:
    candidates: Final = (
        ("api_key", user_api_key_dict.tpd_limit),
        ("team", user_api_key_dict.team_tpd_limit),
        ("team_member", user_api_key_dict.team_member_tpd_limit),
    )
    return tuple(
        DailyTokenScope(name=name, value=value, limit=limit)
        for name, limit in candidates
        if limit is not None
        and (
            value := _scope_value(name, user_api_key_dict.team_id, user_api_key_dict.user_id, user_api_key_dict.api_key)
        )
    )


def charged_scopes(metadata: _LoggedMetadata) -> tuple[tuple[str, str], ...]:
    return tuple(
        (name, value)
        for name in ("api_key", "team", "team_member")
        if (
            value := _scope_value(
                name, metadata.user_api_key_team_id, metadata.user_api_key_user_id, metadata.user_api_key_hash
            )
        )
    )


def counter_key(scope_name: str, scope_value: str, now: datetime) -> str:
    return f"{{daily_tokens:{scope_name}:{scope_value}}}:{now.astimezone(UTC).date().isoformat()}"


def seconds_until_reset(now: datetime) -> int:
    utc_now: Final = now.astimezone(UTC)
    next_midnight: Final = datetime.combine(utc_now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    return int((next_midnight - utc_now).total_seconds())


class _PROXY_DailyTokenLimiter(CustomLogger):
    def __init__(
        self,
        internal_usage_cache: "InternalUsageCache",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.internal_usage_cache = internal_usage_cache
        self.clock = clock

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,  # mutable-ok: override must match CustomLogger.async_pre_call_hook
        call_type: str,
    ) -> Exception | str | dict | None:  # mutable-ok: override must match CustomLogger.async_pre_call_hook
        if call_type in _BATCH_CALL_TYPES:
            return None
        now: Final = self.clock()
        usages: Final = tuple(
            [
                (scope, await self._read_tokens(counter_key(scope.name, scope.value, now)))
                for scope in limited_scopes(user_api_key_dict)
            ]
        )
        exceeded: Final = next(((scope, used) for scope, used in usages if used >= scope.limit), None)
        if exceeded is None:
            return None
        scope, used = exceeded
        resolved_model, llm_provider = resolve_llm_provider_for_rate_limit(data.get("model"))
        raise ProxyRateLimitError(
            detail=(
                f"Daily token limit reached for {scope.name}. "
                f"Used {used} of {scope.limit} tokens today (UTC). Resets at 00:00 UTC."
            ),
            rate_limit_type=RateLimitType.TOKENS,
            model=resolved_model,
            llm_provider=llm_provider,
            headers={"retry-after": str(seconds_until_reset(now))},
        )

    async def async_log_success_event(
        self, kwargs: object, response_obj: object, start_time: object, end_time: object
    ) -> None:
        if not isinstance(kwargs, Mapping):
            return
        try:
            logged: Final = _LoggedCall.model_validate(kwargs.get("standard_logging_object") or {})
        except ValidationError:
            verbose_proxy_logger.warning("DailyTokenLimiter: unreadable standard_logging_object, tokens not counted")
            return
        if logged.total_tokens <= 0:
            return
        now: Final = self.clock()
        ttl: Final = seconds_until_reset(now) + int(_COUNTER_TTL_SLACK.total_seconds())
        for scope_name, scope_value in charged_scopes(logged.metadata):
            await self.internal_usage_cache.dual_cache.async_increment_cache(
                key=counter_key(scope_name, scope_value, now),
                value=logged.total_tokens,
                ttl=ttl,
            )

    async def _read_tokens(self, key: str) -> int:
        redis_cache: Final = self.internal_usage_cache.dual_cache.redis_cache
        if redis_cache is not None:
            try:
                remote: Final = await redis_cache.async_get_cache(key=key)
                return int(float(remote)) if remote is not None else 0
            except Exception as e:  # noqa: BLE001  # Redis outage falls back to the local counter
                log_redis_failure(verbose_proxy_logger, logging.WARNING, "DailyTokenLimiter: Redis GET failed", e)
        local: Final = await self.internal_usage_cache.async_get_cache(
            key=key, litellm_parent_otel_span=None, local_only=True
        )
        return int(float(local)) if local is not None else 0


PROXY_DailyTokenLimiter: Final = _PROXY_DailyTokenLimiter
