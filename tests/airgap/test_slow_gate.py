from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Final

from tests.airgap.slow_gate import Timing, fastest_alone, over_limit, timings_by_file

FORK_OWNED: Final = frozenset({"a.py"})


def _measurements(*runs: tuple[float, float]) -> tuple[Callable[[str], Timing], list[str]]:
    calls: Final[list[str]] = []  # mutable-ok: records how many solo runs the gate asked for
    queue: Final[Iterator[tuple[float, float]]] = iter(runs)

    def measure(file: str) -> Timing:
        calls.append(file)
        return Timing(file, *next(queue))

    return measure, calls


def test_over_limit_catches_slow_fork_file_or_any_slow_test_slowest_first() -> None:
    timings: Final = (
        Timing("ok.py", 2.9, 1.9),
        Timing("slow_test.py", 2.5, 2.1),
        Timing("slow_file.py", 3.5, 0.5),
        Timing("upstream_big.py", 9.0, 0.5),
        Timing("upstream_slow_test.py", 9.0, 2.5),
    )
    fork_owned: Final = frozenset({"ok.py", "slow_test.py", "slow_file.py"})
    assert [t.file for t in over_limit(timings, fork_owned)] == [
        "upstream_slow_test.py",
        "slow_file.py",
        "slow_test.py",
    ]


def test_fastest_alone_stops_at_the_first_run_within_limits() -> None:
    measure, calls = _measurements((4.0, 1.0), (2.0, 1.0), (1.0, 1.0))
    assert fastest_alone("a.py", measure, FORK_OWNED) == Timing("a.py", 2.0, 1.0)
    assert len(calls) == 2


def test_fastest_alone_keeps_the_minimum_of_each_measure_across_tries() -> None:
    measure, calls = _measurements((5.0, 1.0), (3.5, 2.5), (4.0, 2.2))
    assert fastest_alone("a.py", measure, FORK_OWNED) == Timing("a.py", 3.5, 1.0)
    assert len(calls) == 3


def test_file_time_counts_test_bodies_and_test_time_counts_every_phase() -> None:
    calls: Final = {"tests/unit/a.py::test_x": 1.0, "tests/unit/a.py::test_y": 1.5, "tests/unit/b.py::C::test_z": 0.1}
    totals: Final = {"tests/unit/a.py::test_x": 1.2, "tests/unit/a.py::test_y": 1.6, "tests/unit/b.py::C::test_z": 2.4}
    assert timings_by_file(calls, totals) == (Timing("tests/unit/a.py", 2.5, 1.6), Timing("tests/unit/b.py", 0.1, 2.4))
