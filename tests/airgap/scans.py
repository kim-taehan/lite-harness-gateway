from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from itertools import chain
from typing import Final

URL_HOST: Final = re.compile(r"https?://\[?([A-Za-z0-9.\-_:]+?)\]?(?::\d+)?(?:[/?#\"'\s]|$)")
INTERNAL_HOSTS: Final = frozenset({"localhost", "0.0.0.0", "::1", "host.docker.internal"})
INTERNAL_SUFFIXES: Final = (".local", ".internal", ".svc", ".localhost", ".invalid", ".test", ".example")
LOG_METHODS: Final = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
SECRET_WORDS: Final = frozenset({"token", "secret", "password", "passwd", "authorization", "credential", "credentials"})
KEY_OWNERS: Final = frozenset({"api", "master", "virtual", "private", "secret", "access", "signing"})
SAFE_WORDS: Final = frozenset({"hash", "hashed", "masked", "redacted", "count", "len", "type", "name", "expiry"})


def is_internal_host(host: str) -> bool:
    lowered: Final = host.lower()
    return lowered in INTERNAL_HOSTS or lowered.startswith("127.") or lowered.endswith(INTERNAL_SUFFIXES)


def _touches(node: ast.AST, added_lines: frozenset[int]) -> bool:
    start: Final = getattr(node, "lineno", 0)
    end: Final = getattr(node, "end_lineno", start) or start
    return any(line in added_lines for line in range(start, end + 1))


def external_url_lines(source: str, added_lines: frozenset[int]) -> tuple[int, ...]:
    """Added lines whose string literals point at a host outside the closed network (docstrings excluded)"""
    tree: Final = ast.parse(source)
    docstrings: Final = frozenset(
        id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    )
    literals: Final = (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    )
    hits: Final = (
        node.lineno
        for node in literals
        if _touches(node, added_lines) and any(not is_internal_host(h) for h in URL_HOST.findall(str(node.value)))
    )
    return tuple(sorted(set(hits)))


def is_secret_name(identifier: str) -> bool:
    words: Final = frozenset(re.sub(r"([a-z])([A-Z])", r"\1_\2", identifier).lower().split("_"))
    if words & SAFE_WORDS:
        return False
    return bool(words & SECRET_WORDS) or "apikey" in words or ("key" in words and bool(words & KEY_OWNERS))


def _is_log_call(node: ast.Call) -> bool:
    func: Final = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if not isinstance(func, ast.Attribute) or func.attr not in LOG_METHODS:
        return False
    owner: Final = func.value
    name: Final = owner.id if isinstance(owner, ast.Name) else owner.attr if isinstance(owner, ast.Attribute) else ""
    return name.endswith("logger") or name == "logging"


def _identifiers(node: ast.AST) -> Iterator[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            yield child.id
        elif isinstance(child, ast.Attribute):
            yield child.attr


def secret_logging_lines(source: str, added_lines: frozenset[int]) -> tuple[int, ...]:
    """Added log/print calls that pass a value named like a key, token or password"""
    calls: Final = (
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _is_log_call(node) and _touches(node, added_lines)
    )
    hits: Final = (
        call.lineno
        for call in calls
        if any(map(is_secret_name, chain.from_iterable(map(_identifiers, (*call.args, *call.keywords)))))
    )
    return tuple(sorted(set(hits)))
