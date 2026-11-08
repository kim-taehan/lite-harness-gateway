"""Blocks git commit until /convention-review recorded the current changes (.claude/rules/workflow.md 10번)"""

from __future__ import annotations

from typing import Final

from convention_state import convention_state, state_file
from hooklib import block, find_git_subcommand, run_hook


def check(command: str, cwd: str) -> None:
    if find_git_subcommand(command, "commit") is None:
        return
    stored_file: Final = state_file(cwd)
    stored: Final = stored_file.read_text(encoding="utf-8").strip() if stored_file.exists() else ""
    if not stored or stored != convention_state(cwd):
        block(
            "커밋 전에 규칙 심사가 필요합니다. /convention-review 로 변경을 .claude/rules 와 대조하고, 위반이 없으면 "
            "스킬의 마지막 단계(python3 .claude/hooks/convention_state.py store)를 실행한 뒤 다시 커밋해 주세요"
        )


run_hook(check)
