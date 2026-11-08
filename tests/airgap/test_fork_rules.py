from __future__ import annotations

import re
from itertools import chain
from pathlib import Path
from typing import Final

from tests.airgap.baseline import check_baseline
from tests.airgap.fork_diff import REPO_ROOT, fork_files, mirror_tests
from tests.airgap.scans import external_url_lines, secret_logging_lines

RULES_DIR: Final = REPO_ROOT / ".claude" / "rules"
REQUIRED_RULE: Final = re.compile(r"^\d+\. \*\*\[필수\]")
CHECK_PATH: Final = re.compile(r"`((?:tests|scripts|\.claude|\.github)/[^`\s]+)`")


def _source(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_upstream_files_touched_only_as_much_as_the_baseline() -> None:
    footprint: Final = {f.path: f.added + f.deleted for f in fork_files() if f.status in ("M", "D")}
    assert not check_baseline("upstream_footprint", footprint)


def test_fork_code_adds_no_external_hosts() -> None:
    counts: Final = {
        f.path: len(external_url_lines(_source(f.path), f.added_lines)) for f in fork_files() if f.is_python_source
    }
    assert not check_baseline("external_urls", counts)


def test_fork_code_does_not_log_secrets() -> None:
    counts: Final = {
        f.path: len(secret_logging_lines(_source(f.path), f.added_lines)) for f in fork_files() if f.is_python_source
    }
    assert not check_baseline("secret_logging", counts)


def test_fork_sources_have_mirror_unit_tests() -> None:
    sources: Final = (
        f.path
        for f in fork_files()
        if f.is_python_source and f.path.startswith("litellm/") and not f.path.endswith("__init__.py")
    )
    missing: Final = {path: 1 for path in sources if not mirror_tests(path)}
    assert not check_baseline("missing_mirror_tests", missing)


def test_fork_adds_no_dependencies() -> None:
    changed: Final = tuple(f.path for f in fork_files() if f.path in ("pyproject.toml", "uv.lock"))
    assert not changed, f"의존성 파일이 바뀌었습니다: {changed}. code-quality.md 1번을 보세요"


def _required_rules(path: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.name, line) for line in path.read_text(encoding="utf-8").splitlines() if REQUIRED_RULE.match(line)
    )


def _missing_checks(name: str, line: str) -> tuple[str, ...]:
    targets: Final = CHECK_PATH.findall(line.rsplit("— ", 1)[-1])
    return tuple(f"{name}: {target}" for target in targets if not (REPO_ROOT / target.split("::")[0]).exists())


def test_every_required_rule_names_an_existing_check() -> None:
    rules: Final = tuple(chain.from_iterable(map(_required_rules, sorted(RULES_DIR.glob("*.md")))))
    unnamed: Final = tuple(f"{name}: {line[:60]}" for name, line in rules if "— " not in line)
    missing: Final = tuple(chain.from_iterable(_missing_checks(name, line) for name, line in rules))
    assert rules, "규칙 파일에 [필수] 규칙이 없습니다"
    assert not unnamed, f"[필수] 규칙 끝에 검사 위치(— tests/... 또는 — 커밋 심사)가 없습니다: {unnamed}"
    assert not missing, f"[필수] 규칙이 가리키는 검사 파일이 없습니다: {missing}"


UPSTREAM_HARNESS: Final = re.compile(
    r"^(AGENTS\.md|\.github/workflows/(?!airgap-ci\.yml$).+|scripts/(?:[a-z_]+_gate|gate_slot_lock|lint_base_counts|check_[a-z_]+)\.py)$"
)


def test_fork_leaves_upstream_rules_workflows_and_gates_alone() -> None:
    touched: Final = tuple(f.path for f in fork_files() if f.status != "A" and UPSTREAM_HARNESS.match(f.path))
    assert not touched, f"upstream 규칙·워크플로·게이트를 고쳤습니다: {touched}. architecture.md 4번을 보세요"
