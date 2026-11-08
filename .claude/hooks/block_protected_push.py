"""Blocks a direct push to main or litellm_airgap (.claude/rules/workflow.md 5번)"""

from __future__ import annotations

import os
import subprocess
from typing import Final

from hooklib import block, git, leading_dir, push_command_verdict, run_hook


def check(command: str, cwd: str) -> None:
    base_dir: Final = leading_dir(command, cwd)

    def branch_for(dash_c: str | None) -> str:
        directory: Final = os.path.normpath(os.path.join(base_dir, dash_c)) if dash_c else base_dir
        try:
            return git(directory, "branch", "--show-current").strip()
        except subprocess.CalledProcessError:
            return ""

    verdict: Final = push_command_verdict(command, branch_for)
    if not verdict.ok:
        block(verdict.reason)


run_hook(check, follow_git_dash_c=False)
