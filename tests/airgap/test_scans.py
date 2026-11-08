from __future__ import annotations

from typing import Final

import pytest

from tests.airgap.baseline import compare
from tests.airgap.scans import external_url_lines, is_secret_name, secret_logging_lines

ALL_LINES: Final = frozenset(range(1, 100))


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:4000/v1",
        "http://127.0.0.1:11434",
        "http://[::1]:8080/x",
        "http://host.docker.internal:11434",
        "http://keycloak.internal/realms/litellm",
        "https://gateway.svc/health",
    ],
)
def test_internal_hosts_are_allowed(url: str) -> None:
    assert external_url_lines(f'URL = "{url}"\n', ALL_LINES) == ()


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "http://telemetry.example.com", "https://8.8.8.8/x"])
def test_external_hosts_are_reported(url: str) -> None:
    assert external_url_lines(f'x = 1\nURL = f"{url}/{{path}}"\n', ALL_LINES) == (2,)


def test_external_host_in_docstring_is_not_a_request() -> None:
    source: Final = 'def f():\n    """See https://docs.litellm.ai for details"""\n    return 1\n'
    assert external_url_lines(source, ALL_LINES) == ()


def test_only_added_lines_count() -> None:
    source: Final = 'A = "https://api.openai.com"\nB = "https://api.anthropic.com"\n'
    assert external_url_lines(source, frozenset({2})) == (2,)


@pytest.mark.parametrize(
    "name",
    ["api_key", "master_key", "access_token", "id_token", "client_secret", "password", "authorization", "apiKey"],
)
def test_secret_names(name: str) -> None:
    assert is_secret_name(name)


@pytest.mark.parametrize(
    "name", ["hashed_token", "token_count", "total_tokens", "max_tokens", "key_alias", "masked_api_key", "user_id"]
)
def test_non_secret_names(name: str) -> None:
    assert not is_secret_name(name)


def test_logging_a_secret_is_reported() -> None:
    source: Final = (
        "def f(api_key, user_id):\n"
        "    verbose_proxy_logger.debug(f'key={api_key}')\n"
        "    logger.info('user %s', user_id)\n"
        "    print(request.headers.authorization)\n"
        "    logging.warning('x', extra={'token': token})\n"
    )
    assert secret_logging_lines(source, ALL_LINES) == (2, 4, 5)


def test_non_logging_calls_with_secrets_are_ignored() -> None:
    source: Final = "def f(api_key):\n    client.error(api_key)\n    return send(api_key)\n"
    assert secret_logging_lines(source, ALL_LINES) == ()


def test_baseline_rejects_growth_and_new_files() -> None:
    problems: Final = compare({"a.py": 2}, {"a.py": 3, "b.py": 1})
    assert len(problems) == 2
    assert "a.py: 2 -> 3" in problems[0]
    assert "b.py: 0 -> 1" in problems[1]


def test_baseline_asks_to_be_lowered_when_violations_shrink() -> None:
    problems: Final = compare({"a.py": 2, "gone.py": 1}, {"a.py": 1})
    assert len(problems) == 2
    assert all("기준선을 낮춰" in problem for problem in problems)


def test_baseline_passes_when_equal() -> None:
    assert compare({"a.py": 2}, {"a.py": 2}) == ()
