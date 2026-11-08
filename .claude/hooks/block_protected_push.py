"""Blocks a direct push to main or litellm_airgap (.claude/rules/workflow.md 5번)"""

from __future__ import annotations

from typing import Final

from hooklib import block, find_git_subcommand, git, protected_push_verdict, run_hook


def check(command: str, cwd: str) -> None:
    args: Final = find_git_subcommand(command, "push")
    if args is None:
        return
    verdict: Final = protected_push_verdict(args, git(cwd, "branch", "--show-current").strip())
    if not verdict.ok:
        block(verdict.reason)


run_hook(check)
