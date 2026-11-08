from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

BASELINE_DIR: Final = Path(__file__).parent / "baseline"
UPDATE_ENV: Final = "UPDATE_AIRGAP_BASELINE"


def compare(stored: Mapping[str, int], current: Mapping[str, int]) -> tuple[str, ...]:
    grown: Final = tuple(
        f"{path}: {stored.get(path, 0)} -> {count} (늘었다)"
        for path, count in sorted(current.items())
        if count > stored.get(path, 0)
    )
    shrunk: Final = tuple(
        f"{path}: {count} -> {current.get(path, 0)} (줄었다, 기준선을 낮춰 주세요)"
        for path, count in sorted(stored.items())
        if current.get(path, 0) < count
    )
    return grown + shrunk


def check_baseline(name: str, current: Mapping[str, int]) -> tuple[str, ...]:
    path: Final = BASELINE_DIR / f"{name}.json"
    nonzero: Final = {key: value for key, value in sorted(current.items()) if value}
    if os.environ.get(UPDATE_ENV) == "1":
        BASELINE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(nonzero, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return ()
    stored: Final = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    problems: Final = compare(stored, nonzero)
    if not problems:
        return ()
    return (
        *problems,
        f"고친 뒤 기준선이 맞으면 {UPDATE_ENV}=1 로 다시 돌려 tests/airgap/baseline/{name}.json 을 갱신하세요",
    )
