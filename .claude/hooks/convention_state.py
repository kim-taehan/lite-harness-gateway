"""Fingerprint of what /convention-review approved: staged diff, unstaged diff, untracked files and .claude/rules

  python3 .claude/hooks/convention_state.py          print the current fingerprint
  python3 .claude/hooks/convention_state.py store    record it as reviewed

The record lives in the git dir of the checkout, so it is per worktree and never committed
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Final

from hooklib import git


def state_file(cwd: str) -> Path:
    return Path(cwd) / git(cwd, "rev-parse", "--git-path", "airgap-convention-state").strip()


def _untracked_part(root: Path, name: str) -> bytes:
    path: Final = root / name
    if path.is_symlink():
        return f"{name}\0link:{os.readlink(path)}\0".encode()
    if path.is_file():
        return f"{name}\0{hashlib.sha256(path.read_bytes()).hexdigest()}\0".encode()
    return b""


def convention_state(cwd: str) -> str:
    root: Final = Path(git(cwd, "rev-parse", "--show-toplevel").strip())
    untracked: Final = sorted(n for n in git(cwd, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if n)
    rules: Final = sorted((root / ".claude" / "rules").glob("*.md"))
    parts: Final = (
        git(cwd, "diff", "--cached").encode(),
        git(cwd, "diff").encode(),
        *(_untracked_part(root, name) for name in untracked),
        *(rule.name.encode() + rule.read_bytes() for rule in rules),
    )
    return hashlib.sha256(b"".join(parts)).hexdigest()[:16]


if __name__ == "__main__":
    here: Final = os.getcwd()
    state: Final = convention_state(here)
    if sys.argv[1:] == ["store"]:
        state_file(here).write_text(state + "\n", encoding="utf-8")
    sys.stdout.write(state + "\n")
