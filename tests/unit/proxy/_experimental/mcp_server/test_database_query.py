"""
Tests for the MCP gateway's read-only PostgreSQL query tool (query_database).

Covers:
- validate_database_query_sql: single SELECT statements pass, DML/DDL, multiple statements,
  dangerous calls, and unterminated literals fail, while keyword-like text inside string
  literals, quoted identifiers, comments, and dollar-quoted strings is ignored
- handle_database_query: admin gate, database-connection gate, read-only transaction with
  statement timeout, LIMIT capping, result size cap, and error conversion to is_error results
- tools/call dispatch routes query_database straight to its handler (no tool-search flag) and
  /mcp/proxy rejects it
- tools/list advertises query_database only to proxy admins with mcp_tool_search_enabled
"""

from typing import Any, Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm.models.object_permission import LiteLLM_ObjectPermissionTable
from litellm.proxy._experimental.mcp_server import operations as mcp_operations
from litellm.proxy._experimental.mcp_server.database_query import (
    DATABASE_QUERY_TOOL_NAME,
    DEFAULT_DATABASE_QUERY_LIMIT,
    MAX_DATABASE_QUERY_LIMIT,
    database_query_tool_definition,
    handle_database_query,
    validate_database_query_sql,
)
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth


def _make_perm(**kwargs: Any) -> LiteLLM_ObjectPermissionTable:
    return LiteLLM_ObjectPermissionTable(object_permission_id="test", **kwargs)


def _admin(**kwargs: Any) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(api_key="k", user_role=LitellmUserRoles.PROXY_ADMIN, **kwargs)


def _user(**kwargs: Any) -> UserAPIKeyAuth:
    return UserAPIKeyAuth(api_key="k", user_role=LitellmUserRoles.INTERNAL_USER, **kwargs)


@pytest.mark.parametrize(
    "sql",
    (
        'SELECT * FROM "LiteLLM_SpendLogs" LIMIT 5',
        "select 1",
        'WITH recent AS (SELECT request_id FROM "LiteLLM_SpendLogs" ORDER BY start_time DESC LIMIT 10) SELECT * FROM recent',
        "SELECT 'DROP TABLE users; DELETE FROM keys' AS note, 1 AS n",
        "SELECT $$INSERT INTO x VALUES (1);$$ AS body",
        "SELECT $tag$with; semicolons and drop table statements$tag$ FROM t",
        "SELECT /* INSERT UPDATE DELETE */ 1 AS v",
        "SELECT /* outer /* inner */ still comment */ 1 AS v",
        "SELECT 'line comment inside a string' -- trailing; delete; \nFROM t",
        "SELECT 'a ; b' FROM t",
        'SELECT "delete", "update", "setconfig" FROM "table"',
        "SELECT * FROM t WHERE note = 'a''b';",
        "SELECT * FROM t WHERE a = $1",
        "SELECT 1 -- trailing line comment to end of input",
        "SELECT 'unterminated-looking $tag$ inside a normal string' AS s",
    ),
)
def test_single_select_statements_pass(sql: str) -> None:
    assert validate_database_query_sql(sql) is None


@pytest.mark.parametrize(
    ("sql", "message"),
    (
        ("DROP TABLE x", "Only SELECT statements are allowed"),
        ("INSERT INTO t VALUES (1)", "Only SELECT statements are allowed"),
        ("UPDATE t SET a = 1", "Only SELECT statements are allowed"),
        ("DELETE FROM t", "Only SELECT statements are allowed"),
        ("TRUNCATE t", "Only SELECT statements are allowed"),
        ("COPY t TO '/tmp/x'", "Only SELECT statements are allowed"),
        ("EXPLAIN SELECT 1", "Only SELECT statements are allowed"),
        ("CREATE TABLE t (a int)", "Only SELECT statements are allowed"),
        ("SELECT 1; SELECT 2", "Only a single statement is allowed"),
        (";SELECT 1", "Only a single statement is allowed"),
        ("SELECT 'a;b'; SELECT 2", "Only a single statement is allowed"),
        ("WITH d AS (DELETE FROM t RETURNING id) SELECT id FROM d", "'DELETE' is not allowed"),
        ("WITH u AS (UPDATE t SET a = 1 RETURNING id) SELECT * FROM u", "'UPDATE' is not allowed"),
        ("WITH i AS (INSERT INTO t (a) VALUES (1) RETURNING id) SELECT * FROM i", "'INSERT' is not allowed"),
        ("SELECT * INTO new_t FROM t", "'INTO' is not allowed"),
        ("SELECT set_config('statement_timeout', '0', false)", "'SET_CONFIG' is not allowed"),
        ("SELECT lo_import('/etc/passwd')", "'LO_IMPORT' is not allowed"),
        ("SELECT dblink('dbname=litellm', 'select 1')", "'DBLINK' is not allowed"),
        ("SELECT pg_read_file('/etc/passwd')", "'PG_READ_FILE' is not allowed"),
        ("SELECT pg_terminate_backend(1)", "'PG_TERMINATE_BACKEND' is not allowed"),
        ("SELECT 'abc", "unterminated string literal"),
        ('SELECT "abc', "unterminated quoted identifier"),
        ("SELECT 1 /* open", "unterminated block comment"),
        ("SELECT $q$abc", "unterminated dollar-quoted string"),
        ("SELECT $$abc", "unterminated dollar-quoted string"),
        ("   ", "Query must be a SELECT statement"),
        ("", "Query must be a SELECT statement"),
    ),
)
def test_rejected_statements_fail_with_a_reason(sql: str, message: str) -> None:
    result = validate_database_query_sql(sql)
    assert result is not None and message in result


def test_oversized_query_is_rejected() -> None:
    result = validate_database_query_sql("SELECT " + "p" * 70_000)
    assert result is not None and "exceeds the limit" in result


def test_definition_exposes_sql_and_limit() -> None:
    definition: Final = database_query_tool_definition()
    assert definition["name"] == DATABASE_QUERY_TOOL_NAME == "query_database"
    assert definition["inputSchema"]["required"] == ["sql"]
    assert definition["inputSchema"]["properties"]["limit"]["default"] == DEFAULT_DATABASE_QUERY_LIMIT


def _fake_prisma(rows: list[Any], failure: Exception | None = None) -> tuple[MagicMock, MagicMock]:
    transaction = MagicMock()
    transaction.execute_raw = AsyncMock()
    transaction.query_raw = AsyncMock(return_value=rows) if failure is None else AsyncMock(side_effect=failure)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=transaction)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    db = MagicMock()
    db.tx = MagicMock(return_value=context_manager)
    return MagicMock(db=db), transaction


@pytest.mark.asyncio
async def test_non_admin_is_rejected_before_database_access() -> None:
    prisma, transaction = _fake_prisma([{"one": 1}])
    with patch(
        "litellm.proxy.proxy_server.prisma_client", prisma
    ):  # test-quality-ok: prisma comes from a proxy_server global; no injection seam
        result = await handle_database_query("SELECT 1", 10, _user())
    assert result.is_error is True
    assert "proxy admin" in result.content[0].text
    transaction.query_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_without_a_key_is_rejected() -> None:
    result = await handle_database_query("SELECT 1", 10, None)
    assert result.is_error is True
    assert "proxy admin" in result.content[0].text


@pytest.mark.asyncio
async def test_disconnected_database_is_reported() -> None:
    with patch("litellm.proxy.proxy_server.prisma_client", None):
        result = await handle_database_query("SELECT 1", 10, _admin())
    assert result.is_error is True
    assert "Database is not connected" in result.content[0].text


@pytest.mark.asyncio
async def test_invalid_sql_never_reaches_the_database() -> None:
    prisma, transaction = _fake_prisma([])
    with patch(
        "litellm.proxy.proxy_server.prisma_client", prisma
    ):  # test-quality-ok: prisma comes from a proxy_server global; no injection seam
        result = await handle_database_query("DELETE FROM t", 10, _admin())
        assert result.is_error is True
        assert "Only SELECT statements are allowed" in result.content[0].text
        transaction.query_raw.assert_not_awaited()
        transaction.execute_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_runs_read_only_with_timeout_and_capped_limit() -> None:
    prisma, transaction = _fake_prisma([{"one": 1}])
    with patch(
        "litellm.proxy.proxy_server.prisma_client", prisma
    ):  # test-quality-ok: prisma comes from a proxy_server global; no injection seam
        result = await handle_database_query("SELECT 1 AS one;", 999_999, _admin())
    assert result.is_error is False
    (statement,) = transaction.query_raw.await_args.args
    assert statement == f"SELECT * FROM (SELECT 1 AS one) AS litellm_mcp_query LIMIT {MAX_DATABASE_QUERY_LIMIT}"
    executed: Final = [call.args[0] for call in transaction.execute_raw.await_args_list]
    assert "SET TRANSACTION READ ONLY" in executed
    assert "SET LOCAL statement_timeout = 5000" in executed
    assert result.content[0].text == '{"rows": [{"one": 1}], "row_count": 1, "limit": 1000}'


@pytest.mark.asyncio
async def test_database_failure_is_converted_to_tool_error() -> None:
    prisma, _transaction = _fake_prisma([], failure=RuntimeError("boom"))
    with patch(
        "litellm.proxy.proxy_server.prisma_client", prisma
    ):  # test-quality-ok: prisma comes from a proxy_server global; no injection seam
        result = await handle_database_query("SELECT 1", 10, _admin())
    assert result.is_error is True
    assert "Query failed: boom" in result.content[0].text


@pytest.mark.asyncio
async def test_result_over_the_size_cap_is_rejected() -> None:
    prisma, _transaction = _fake_prisma([{"value": "x" * 200_000}] * 10)
    with patch(
        "litellm.proxy.proxy_server.prisma_client", prisma
    ):  # test-quality-ok: prisma comes from a proxy_server global; no injection seam
        result = await handle_database_query("SELECT 1", 10, _admin())
    assert result.is_error is True
    assert "too large" in result.content[0].text


class TestDispatchVirtualMcpTool:
    @pytest.mark.asyncio
    async def test_routes_query_database_to_its_handler(self) -> None:
        admin: Final = _admin()
        with (
            patch(  # test-quality-ok: dispatch routing is the subject; the handler is faked like its siblings in test_mcp_tool_search.py
                "litellm.proxy._experimental.mcp_server.database_query.handle_database_query",
                new_callable=AsyncMock,
                return_value="DB_RESULT",
            ) as mock_handler
        ):
            result = await mcp_operations._dispatch_virtual_mcp_tool(
                name=DATABASE_QUERY_TOOL_NAME,
                arguments={"sql": "SELECT 1", "limit": "7"},
                user_api_key_auth=admin,
                client_ip=None,
            )
        assert result == "DB_RESULT"
        kwargs: Final = mock_handler.await_args.kwargs
        assert kwargs["sql"] == "SELECT 1"
        assert kwargs["limit"] == 7
        assert kwargs["user_api_key_dict"] is admin

    @pytest.mark.asyncio
    async def test_uses_default_limit_when_missing(self) -> None:
        with (
            patch(  # test-quality-ok: dispatch routing is the subject; the handler is faked like its siblings in test_mcp_tool_search.py
                "litellm.proxy._experimental.mcp_server.database_query.handle_database_query",
                new_callable=AsyncMock,
                return_value="DB_RESULT",
            ) as mock_handler
        ):
            await mcp_operations._dispatch_virtual_mcp_tool(
                name=DATABASE_QUERY_TOOL_NAME,
                arguments={"sql": "SELECT 1"},
                user_api_key_auth=_admin(),
                client_ip=None,
            )
        assert mock_handler.await_args.kwargs["limit"] == DEFAULT_DATABASE_QUERY_LIMIT

    @pytest.mark.asyncio
    async def test_forwards_non_admins_to_the_handler_for_rejection(self) -> None:
        with patch(  # test-quality-ok: dispatch routing is the subject; the admin gate lives in the handler
            "litellm.proxy._experimental.mcp_server.database_query.handle_database_query",
            new_callable=AsyncMock,
            return_value="DB_RESULT",
        ) as mock_handler:
            result = await mcp_operations._dispatch_virtual_mcp_tool(
                name=DATABASE_QUERY_TOOL_NAME,
                arguments={"sql": "SELECT 1"},
                user_api_key_auth=_user(),
                client_ip=None,
            )
        assert result == "DB_RESULT"
        assert mock_handler.await_args.kwargs["user_api_key_dict"].user_role == LitellmUserRoles.INTERNAL_USER

    @pytest.mark.asyncio
    async def test_proxy_mode_rejects_query_database(self) -> None:
        result = await mcp_operations._dispatch_virtual_mcp_tool(
            name=DATABASE_QUERY_TOOL_NAME,
            arguments={"sql": "SELECT 1"},
            user_api_key_auth=_admin(),
            client_ip=None,
            mcp_proxy_mode=True,
        )
        assert result is not None
        assert result.is_error is True
        assert "unavailable on /mcp/proxy" in result.content[0].text

    @pytest.mark.asyncio
    async def test_unknown_tools_still_fall_through(self) -> None:
        result = await mcp_operations._dispatch_virtual_mcp_tool(
            name="github-create_issue",
            arguments={},
            user_api_key_auth=_admin(),
            client_ip=None,
        )
        assert result is None


class TestToolslisting:
    @pytest.mark.asyncio
    async def test_advertises_query_database_only_to_admins_with_the_flag(self) -> None:
        from mcp.types import ListToolsRequest

        from litellm.proxy._experimental.mcp_server.operations import GatewayOperations, prepare_context

        async def unused_allowed(*_args: Any, **_kwargs: Any) -> list[Any]:
            return []

        with patch.object(mcp_operations, "_get_allowed_mcp_servers", AsyncMock(side_effect=unused_allowed)):
            admin_listing = await GatewayOperations().execute(
                ListToolsRequest(),
                prepare_context(_admin(object_permission=_make_perm(mcp_tool_search_enabled=True))),
            )
            user_listing = await GatewayOperations().execute(
                ListToolsRequest(),
                prepare_context(_user(object_permission=_make_perm(mcp_tool_search_enabled=True))),
            )
            plain_listing = await GatewayOperations().execute(
                ListToolsRequest(),
                prepare_context(_admin()),
            )

        admin_names: Final = {tool.name for tool in admin_listing.tools}
        user_names: Final = {tool.name for tool in user_listing.tools}
        assert admin_names == {"mcp_tool_search", "mcp_tool_call", "agent_search", "skill_search", "query_database"}
        assert user_names == {"mcp_tool_search", "mcp_tool_call", "agent_search", "skill_search"}
        assert "query_database" not in {tool.name for tool in plain_listing.tools}
