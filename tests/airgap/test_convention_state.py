from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

HOOKS_DIR: Final = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _load(name: str) -> object:
    spec: Final = importlib.util.spec_from_file_location(name, HOOKS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module: Final = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("hooklib")
convention_state: Final = _load("convention_state")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path, check=True, capture_output=True
        )

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "workflow.md").write_text("1. rule\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return tmp_path


def _state(repo: Path) -> str:
    return convention_state.convention_state(str(repo))  # pyright: ignore[reportAttributeAccessIssue]  # module loaded from a file path


def test_state_is_stable_without_changes(repo: Path) -> None:
    assert _state(repo) == _state(repo)


@pytest.mark.parametrize(
    ("path", "content"),
    [("a.py", "x = 2\n"), ("new_file.py", "y = 1\n"), (".claude/rules/workflow.md", "1. changed rule\n")],
)
def test_state_changes_with_edits_new_files_and_rules(repo: Path, path: str, content: str) -> None:
    before: Final = _state(repo)
    (repo / path).write_text(content, encoding="utf-8")
    assert _state(repo) != before


def test_stored_state_lives_in_the_git_dir(repo: Path) -> None:
    assert convention_state.state_file(str(repo)).parent == repo / ".git"  # pyright: ignore[reportAttributeAccessIssue]  # module loaded from a file path
