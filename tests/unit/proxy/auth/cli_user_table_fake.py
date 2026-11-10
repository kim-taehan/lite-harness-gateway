"""An in-memory user table for the CLI single-device tests: the ``litellm_usertable`` actions the
per-request user read and the login record use, over one stored row."""

import json
from collections.abc import Mapping
from typing import Final

from litellm.proxy._types import LiteLLM_UserTable


class FakeUserTable:
    def __init__(self, row: LiteLLM_UserTable | None) -> None:
        self.row = row

    async def find_unique(self, where: Mapping[str, object], include: object = None) -> LiteLLM_UserTable | None:
        return self.row if self.row is not None and where.get("user_id") == self.row.user_id else None

    async def update(self, where: Mapping[str, object], data: Mapping[str, object]) -> LiteLLM_UserTable | None:
        if self.row is None or where.get("user_id") != self.row.user_id:
            return None
        metadata: Final = data["metadata"]
        assert isinstance(metadata, str)
        self.row = self.row.model_copy(update={"metadata": json.loads(metadata)})
        return self.row


class _FakeDb:
    def __init__(self, table: FakeUserTable) -> None:
        self.litellm_usertable = table


class FakePrisma:
    def __init__(self, row: LiteLLM_UserTable | None) -> None:
        self.table = FakeUserTable(row)
        self.db = _FakeDb(self.table)
        self.writer_db = self.db
