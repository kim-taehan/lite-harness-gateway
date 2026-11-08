"""Fails the run when a fork-created unit test file spends over 3s in test bodies or any single test takes over 2s

Load with `pytest -p tests.airgap.slow_gate`. A busy machine stretches timings, so files over the limit are rerun
alone up to RECHECK_TRIES times and judged by the fastest run. The limits stay fixed so failures stay predictable
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import accumulate, repeat
from pathlib import Path
from typing import Final

import pytest

from tests.airgap.fork_diff import fork_files

SLOW_FILE_SECONDS: Final = 3.0
SLOW_TEST_SECONDS: Final = 2.0
RECHECK_TRIES: Final = 3
RECHECK_ENV: Final = "AIRGAP_SLOW_RECHECK"
_CALLS: Final[defaultdict[str, float]] = defaultdict(float)  # mutable-ok: pytest reports arrive one phase at a time
_TOTALS: Final[defaultdict[str, float]] = defaultdict(float)  # mutable-ok: pytest reports arrive one phase at a time


@dataclass(frozen=True, slots=True)
class Timing:
    file: str
    file_seconds: float
    test_seconds: float


def is_slow(timing: Timing, fork_owned: frozenset[str]) -> bool:
    file_too_slow: Final = timing.file in fork_owned and timing.file_seconds > SLOW_FILE_SECONDS
    return file_too_slow or timing.test_seconds > SLOW_TEST_SECONDS


def over_limit(timings: Iterable[Timing], fork_owned: frozenset[str]) -> tuple[Timing, ...]:
    """The file limit only applies to test files the fork created, since upstream owns the rest"""
    return tuple(sorted((t for t in timings if is_slow(t, fork_owned)), key=lambda t: -t.file_seconds))


def _until_fast(bests: Iterable[Timing], fork_owned: frozenset[str]) -> Iterator[Timing]:
    for best in bests:
        yield best
        if not is_slow(best, fork_owned):
            return


def fastest_alone(
    file: str, measure: Callable[[str], Timing], fork_owned: frozenset[str], tries: int = RECHECK_TRIES
) -> Timing:
    """Fastest of up to `tries` solo runs, stopping as soon as one fits the limits"""
    runs: Final = map(measure, repeat(file, tries))
    bests: Final = accumulate(
        runs,
        lambda best, run: Timing(
            file, min(best.file_seconds, run.file_seconds), min(best.test_seconds, run.test_seconds)
        ),
    )
    return tuple(_until_fast(bests, fork_owned))[-1]


def timings_by_file(calls: Mapping[str, float], totals: Mapping[str, float]) -> tuple[Timing, ...]:
    """File time sums test bodies only. Upstream's autouse fixtures cost ~30ms of setup per test, which we cannot
    shrink, so counting setup would just cap the number of tests per file. A single test keeps all its phases"""
    files: Final = sorted({_file_of(nodeid) for nodeid in totals})
    return tuple(
        Timing(file, _sum_for(file, calls), max((v for k, v in totals.items() if _file_of(k) == file), default=0.0))
        for file in files
    )


def _file_of(nodeid: str) -> str:
    return nodeid.split("::")[0]


def _sum_for(file: str, durations: Mapping[str, float]) -> float:
    return sum(seconds for nodeid, seconds in durations.items() if _file_of(nodeid) == file)


def _time_alone(file: str) -> Timing:
    with tempfile.TemporaryDirectory() as directory:
        report: Final = Path(directory) / "timing.json"
        subprocess.run(  # test-quality-ok: the recheck imports this plugin from the checkout via -m, like the parent run
            [sys.executable, "-m", "pytest", file, "-q", "-p", "tests.airgap.slow_gate", "-p", "no:cacheprovider"],
            env={**os.environ, RECHECK_ENV: str(report)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if not report.exists():
            return Timing(file, 0.0, 0.0)
        data: Final = json.loads(report.read_text(encoding="utf-8"))
        return Timing(file, float(data["file_seconds"]), float(data["test_seconds"]))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    _TOTALS[report.nodeid] += report.duration
    if report.when == "call":
        _CALLS[report.nodeid] += report.duration


def pytest_sessionfinish(session: pytest.Session) -> None:
    config: Final = session.config
    if hasattr(config, "workerinput"):
        return
    timings: Final = timings_by_file(_CALLS, _TOTALS)
    recheck_report: Final = os.environ.get(RECHECK_ENV)
    if recheck_report:
        worst: Final = max(timings, key=lambda t: t.file_seconds, default=Timing("", 0.0, 0.0))
        Path(recheck_report).write_text(
            json.dumps({"file_seconds": worst.file_seconds, "test_seconds": worst.test_seconds}), encoding="utf-8"
        )
        return
    fork_owned: Final = frozenset(f.path for f in fork_files() if f.status == "A")
    suspects: Final = over_limit(timings, fork_owned)
    slow: Final = over_limit((fastest_alone(t.file, _time_alone, fork_owned) for t in suspects), fork_owned)
    if not slow:
        return
    lines: Final = (
        f"\n느린 단위 테스트 {len(slow)}개. 혼자 {RECHECK_TRIES}번까지 돌려도 fork 가 만든 파일 {SLOW_FILE_SECONDS:g}초, "
        f"테스트 하나 {SLOW_TEST_SECONDS:g}초를 넘습니다 (.claude/rules/code-quality.md 7번)",
        *(f"  파일 {t.file_seconds:.2f}초, 가장 긴 테스트 {t.test_seconds:.2f}초  {t.file}" for t in slow),
        "가짜 시계나 가짜 의존으로 바꾸거나, 실물이 필요하면 tests/e2e/ 로 옮겨 주세요\n",
    )
    sys.stderr.write("\n".join(lines))
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
