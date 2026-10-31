from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Final, Protocol

from litellm._logging import verbose_logger
from litellm.types.proxy.auth.user_api_key_auth import user_api_key_has_admin_view

if TYPE_CHECKING:
    from mcp.types import CallToolResult

    from litellm.proxy._types import UserAPIKeyAuth

from litellm.proxy._experimental.mcp_server.tool_search import VirtualToolDefinition

DATABASE_QUERY_TOOL_NAME: Final[str] = "query_database"
DEFAULT_DATABASE_QUERY_LIMIT: Final[int] = 100
MAX_DATABASE_QUERY_LIMIT: Final[int] = 1000
MAX_DATABASE_QUERY_CHARS: Final[int] = 64_000
DATABASE_QUERY_STATEMENT_TIMEOUT_MS: Final[int] = 5_000
_DATABASE_QUERY_TRANSACTION_TIMEOUT: Final = timedelta(seconds=10)
MAX_DATABASE_QUERY_RESULT_CHARS: Final[int] = 1_048_576
_DATABASE_QUERY_RESULT_ALIAS: Final[str] = "litellm_mcp_query"

_ALLOWED_LEADING_WORDS: Final = frozenset({"select", "with"})

_FORBIDDEN_WORDS: Final = frozenset(
    {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "grant",
        "revoke",
        "attach",
        "detach",
        "comment",
        "vacuum",
        "analyze",
        "refresh",
        "cluster",
        "reindex",
        "reassign",
        "security",
        "lock",
        "unlock",
        "checkpoint",
        "listen",
        "notify",
        "publish",
        "subscribe",
        "begin",
        "commit",
        "rollback",
        "abort",
        "savepoint",
        "release",
        "set",
        "reset",
        "call",
        "do",
        "prepare",
        "execute",
        "deallocate",
        "declare",
        "fetch",
        "move",
        "close",
        "perform",
        "discard",
        "into",
        "copy",
        "set_config",
        "lo_import",
        "lo_export",
        "lo_unlink",
        "dblink",
        "dblink_connect",
        "dblink_exec_query",
        "pg_read_file",
        "pg_ls_dir",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "pg_reload_conf",
        "pg_rotate_copy_stat",
        "pg_load_lib",
    }
)

_WORD_RE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOLLAR_QUOTE_RE: Final = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")


def _skip_block_comment(sql: str, i: int, n: int) -> int:
    depth = 1  # rebind-ok: PostgreSQL block comments nest, so the depth tracks each /* pair
    while i < n:
        if sql.startswith("/*", i):
            depth += 1
            i += 2
        elif sql.startswith("*/", i):
            depth -= 1
            i += 2
            if depth == 0:
                break
        else:
            i += 1
    return i if depth == 0 else -1


def _scan_sql(sql: str) -> tuple[tuple[str, ...], tuple[int, ...], str | None]:
    """Code words and semicolon positions of ``sql`` with string literals, quoted identifiers,
    and comments removed from the picture, so keyword checks see only executable SQL. The third
    item names an unterminated construct, else ``None``."""
    words: Final[list[str]] = []  # mutable-ok: the scanner appends code words as the cursor passes them
    semicolons: Final[list[int]] = []  # mutable-ok: the scanner appends semicolon positions as the cursor passes them
    state = "code"  # rebind-ok: the scanner walks one construct at a time and moves between them
    dollar_tag = ""  # rebind-ok: holds the open delimiter while the cursor is inside a dollar-quoted string
    i = 0  # rebind-ok: scan cursor
    n: Final = len(sql)
    while i < n:
        if state == "code":
            if sql.startswith("--", i):
                end = sql.find("\n", i + 2)
                i = n if end < 0 else end + 1
                continue
            if sql.startswith("/*", i):
                end = _skip_block_comment(sql, i + 2, n)
                if end < 0:
                    return (), (), "unterminated block comment"
                i = end
                continue
            char = sql[i]
            if char == "'":
                state = "squote"
                i += 1
                continue
            if char == '"':
                state = "dquote"
                i += 1
                continue
            if char == "$":
                tag = _DOLLAR_QUOTE_RE.match(sql, i)
                if tag is not None:
                    dollar_tag = tag.group(0)
                    state = "dollar"
                    i += len(dollar_tag)
                    continue
            if char == ";":
                semicolons.append(i)
                i += 1
                continue
            word = _WORD_RE.match(sql, i)
            if word is not None:
                words.append(word.group(0))
                i += len(word.group(0))
                continue
            i += 1
        elif state == "squote":
            end = sql.find("'", i)
            if end < 0:
                return (), (), "unterminated string literal"
            if sql.startswith("''", end):
                i = end + 2
                continue
            state = "code"
            i = end + 1
        elif state == "dquote":
            end = sql.find('"', i)
            if end < 0:
                return (), (), "unterminated quoted identifier"
            if sql.startswith('""', end):
                i = end + 2
                continue
            state = "code"
            i = end + 1
        else:
            end = sql.find(dollar_tag, i)
            if end < 0:
                return (), (), "unterminated dollar-quoted string"
            state = "code"
            i = end + len(dollar_tag)
    return tuple(words), tuple(semicolons), None


def validate_database_query_sql(sql: str) -> str | None:
    if len(sql) > MAX_DATABASE_QUERY_CHARS:
        return f"Query exceeds the limit of {MAX_DATABASE_QUERY_CHARS} characters"
    words, semicolons, scan_error = _scan_sql(sql)
    if scan_error is not None:
        return scan_error
    body: Final = sql.rstrip()
    if not body:
        return "Query must be a SELECT statement"
    if body.endswith(";"):
        if len(semicolons) != 1 or semicolons[0] != len(body) - 1:
            return "Only a single statement is allowed"
    elif semicolons:
        return "Only a single statement is allowed"
    if not words or words[0].lower() not in _ALLOWED_LEADING_WORDS:
        return "Only SELECT statements are allowed (WITH ... SELECT is supported)"
    for word in words:
        if word.lower() in _FORBIDDEN_WORDS:
            return f"'{word.upper()}' is not allowed in a read-only query. If it names a column or table, wrap it in double quotes."
    return None


def _normalized_statement(sql: str) -> str:
    body: Final = sql.rstrip()
    return body[:-1].rstrip() if body.endswith(";") else body


class _DbQueryTxClient(Protocol):
    async def execute_raw(self, query: str, *args: object) -> int: ...

    async def query_raw(self, query: str, *args: object) -> list[dict[str, object]]: ...


class _DbQueryTx(Protocol):
    async def __aenter__(self) -> _DbQueryTxClient: ...

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> bool | None: ...


def _database_query_tool_result(text: str, is_error: bool) -> CallToolResult:
    from mcp.types import CallToolResult, TextContent

    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=is_error)


_DATABASE_QUERY_DEFINITION: Final[VirtualToolDefinition] = {
    "name": DATABASE_QUERY_TOOL_NAME,
    "description": (
        "Run a read-only SQL query (a single SELECT statement) against the LiteLLM PostgreSQL database "
        "and return the rows as JSON. Use it for spend logs, API keys, users, teams, and other LiteLLM "
        "tables. Multiple statements, DML, DDL, and parameter placeholders are rejected."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A single SELECT statement. WITH ... SELECT is supported. No writes, no parameters.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of rows to return.",
                "default": DEFAULT_DATABASE_QUERY_LIMIT,
            },
        },
        "required": ["sql"],
    },
}


def database_query_tool_definition() -> VirtualToolDefinition:
    return _DATABASE_QUERY_DEFINITION


async def handle_database_query(
    sql: str,
    limit: int,
    user_api_key_dict: UserAPIKeyAuth | None,
) -> CallToolResult:
    if user_api_key_dict is None or not user_api_key_has_admin_view(user_api_key_dict):
        return _database_query_tool_result(
            "query_database requires the proxy admin role",
            is_error=True,
        )

    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        return _database_query_tool_result(
            "Database is not connected; query_database requires a proxy with a database",
            is_error=True,
        )

    validation_error: Final = validate_database_query_sql(sql)
    if validation_error is not None:
        return _database_query_tool_result(validation_error, is_error=True)

    row_limit: Final = max(1, min(limit, MAX_DATABASE_QUERY_LIMIT))
    statement: Final = (
        f"SELECT * FROM ({_normalized_statement(sql)}) AS {_DATABASE_QUERY_RESULT_ALIAS} LIMIT {row_limit}"
    )
    try:
        tx: Final[_DbQueryTx] = prisma_client.db.tx(  # pyright: ignore[reportAny]  # prisma wrapper exposes tx untyped
            timeout=_DATABASE_QUERY_TRANSACTION_TIMEOUT
        )
        async with tx as client:
            await client.execute_raw("SET TRANSACTION READ ONLY")
            await client.execute_raw(f"SET LOCAL statement_timeout = {DATABASE_QUERY_STATEMENT_TIMEOUT_MS}")
            rows: Final = await client.query_raw(statement)
    except Exception as e:
        verbose_logger.info("MCP query_database failed: %s", e)
        return _database_query_tool_result(f"Query failed: {e}", is_error=True)

    text: Final = json.dumps({"rows": rows, "row_count": len(rows), "limit": row_limit}, default=str)
    if len(text) > MAX_DATABASE_QUERY_RESULT_CHARS:
        return _database_query_tool_result(
            "Result is too large; select fewer columns or narrow the query",
            is_error=True,
        )
    return _database_query_tool_result(text, is_error=False)
