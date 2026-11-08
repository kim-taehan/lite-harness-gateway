from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from functools import cache
from itertools import chain
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
UPSTREAM_REF: Final = os.environ.get("AIRGAP_UPSTREAM_REF", "origin/main")
SOURCE_ROOTS: Final = ("litellm/", "gateway/", "backend/", "enterprise/")
HUNK: Final = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True, slots=True)
class ForkFile:
    path: str
    status: str
    added: int
    deleted: int
    added_lines: frozenset[int]

    @property
    def is_python_source(self) -> bool:
        return self.path.endswith(".py") and self.path.startswith(SOURCE_ROOTS) and self.status != "D"

    @property
    def is_unit_test(self) -> bool:
        return self.path.startswith("tests/unit/") and Path(self.path).name.startswith("test_") and self.status != "D"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout


def _chunk_added_lines(chunk: str) -> tuple[str, frozenset[int]] | None:
    lines: Final = chunk.splitlines()
    target: Final = next((line.removeprefix("+++ b/") for line in lines if line.startswith("+++ b/")), None)
    if target is None:
        return None
    hunks: Final = tuple(match for match in map(HUNK.match, lines) if match)
    ranges: Final = (range(int(h.group(1)), int(h.group(1)) + int(h.group(2) or "1")) for h in hunks)
    return target, frozenset(chain.from_iterable(ranges))


def _added_lines(patch: str) -> dict[str, frozenset[int]]:
    return dict(filter(None, map(_chunk_added_lines, patch.split("\ndiff --git "))))


def _untracked(base: str) -> tuple[ForkFile, ...]:
    def read(path: str) -> ForkFile:
        try:
            count: Final = len((REPO_ROOT / path).read_text(encoding="utf-8").splitlines())
        except (UnicodeDecodeError, OSError):
            return ForkFile(path, "A", 0, 0, frozenset())
        return ForkFile(path, "A", count, 0, frozenset(range(1, count + 1)))

    names: Final = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return tuple(read(name) for name in names if name and (REPO_ROOT / name).is_file())


@cache
def fork_files() -> tuple[ForkFile, ...]:
    """Everything the fork changed on top of upstream, including uncommitted work in this checkout"""
    base: Final = git("merge-base", UPSTREAM_REF, "HEAD").strip()
    statuses: Final = dict(
        reversed(line.split("\t", 1)) for line in git("diff", "--no-renames", "--name-status", base).splitlines()
    )
    numstat: Final = {
        parts[2]: (int(parts[0]) if parts[0] != "-" else 0, int(parts[1]) if parts[1] != "-" else 0)
        for parts in (line.split("\t", 2) for line in git("diff", "--no-renames", "--numstat", base).splitlines())
    }
    added_lines: Final = _added_lines(git("diff", "--no-renames", "-U0", base))
    tracked: Final = tuple(
        ForkFile(path, status[0], *numstat.get(path, (0, 0)), added_lines.get(path, frozenset()))
        for path, status in sorted(statuses.items())
    )
    return tracked + _untracked(base)


def unit_tests_to_run() -> tuple[str, ...]:
    """Unit test files the fork created or changed. Upstream's own tests run in upstream CI, not here"""
    return tuple(sorted(f.path for f in fork_files() if f.is_unit_test))


def mirror_tests(source: str) -> tuple[Path, ...]:
    relative: Final = Path(source).relative_to("litellm")
    directory: Final = REPO_ROOT / "tests" / "unit" / relative.parent
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob(f"test_*{relative.stem}*.py")))


if __name__ == "__main__":
    parser: Final = argparse.ArgumentParser(description="List files the fork changed on top of upstream")
    parser.add_argument("what", choices=("python-sources", "unit-tests"))
    what: Final = parser.parse_args().what
    if what == "unit-tests":
        print("\n".join(unit_tests_to_run()))
    else:
        print("\n".join(f.path for f in fork_files() if f.is_python_source))
