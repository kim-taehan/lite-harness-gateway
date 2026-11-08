#!/bin/sh
# fork 머지 전 로컬 검사 (.claude/rules/workflow.md 4번). 판정은 종료 코드로만 한다
set -eu
cd "$(git rev-parse --show-toplevel)"
py=.venv/bin/python
ruff=.venv/bin/ruff

sources=$($py -m tests.airgap.fork_diff python-sources)
tests=$($py -m tests.airgap.fork_diff unit-tests)

if [ -n "$sources" ]; then
    echo "$sources" | xargs $ruff check
    echo "$sources" | xargs $ruff format --check
fi
$ruff check .claude/hooks tests/airgap
$ruff format --check .claude/hooks tests/airgap
if [ -n "$tests" ]; then
    echo "$tests" | xargs $ruff check --config ruff-tests.toml
fi

# shellcheck disable=SC2086  # one path per word, paths have no spaces
$py -m pytest tests/airgap $tests -q -p tests.airgap.slow_gate -p no:cacheprovider
