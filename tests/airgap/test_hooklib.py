from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

HOOKS_DIR: Final = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
_spec: Final = importlib.util.spec_from_file_location("hooklib", HOOKS_DIR / "hooklib.py")
assert _spec is not None and _spec.loader is not None
hooklib: Final = importlib.util.module_from_spec(_spec)
sys.modules["hooklib"] = hooklib
_spec.loader.exec_module(hooklib)

MERGE: Final = ("gh", "pr", "merge")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('git commit -m "x"', "/repo"),
        ('cd /tmp/wt && git commit -m "x"', "/tmp/wt"),
        ("cd /tmp/wt; gh pr merge 12 --merge", "/tmp/wt"),
        ('cd "/tmp/my wt" && git commit', "/tmp/my wt"),
        ("cd '/tmp/my wt' && git commit", "/tmp/my wt"),
        ("cd ../wt && git commit", "/wt"),
        ("cd /tmp && cd wt && git commit", "/tmp/wt"),
        ("export PATH=/x/bin:$PATH; cd /tmp/wt && git commit", "/tmp/wt"),
        ('git -C /tmp/wt commit -m "x"', "/tmp/wt"),
        ("cd /tmp && git -C wt push origin a", "/tmp/wt"),
        ("echo hi && cd /tmp/wt && git commit", "/repo"),
    ],
)
def test_command_dir_follows_leading_cd_and_git_dash_c(command: str, expected: str) -> None:
    assert hooklib.command_dir(command, "/repo") == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("gh pr merge 12 --merge", ("12", "--merge")),
        ("cd /tmp/wt && gh pr merge 12", ("12",)),
        ("npm test; gh pr merge 12", ("12",)),
        ("echo a | gh pr merge 12", ("12",)),
        ("npm test\ngh pr merge 12", ("12",)),
        ('PATH=/x:$PATH GH_TOKEN=t gh pr merge 12 --body "검사 통과; 머지"', ("12", "--body", "검사 통과; 머지")),
        ("cat > b.md <<'EOF'\n본문\nEOF\ngh pr merge 12", ("12",)),
        ("/opt/homebrew/bin/gh pr merge 12 --merge", ("12", "--merge")),
        ("cd /tmp/wt && PATH=/x:$PATH /usr/local/bin/gh pr merge 12", ("12",)),
        ("command gh pr merge 12", ("12",)),
        ("exec gh pr merge 12", ("12",)),
        ("env gh pr merge 12", ("12",)),
        ("env -i GH_TOKEN=t /opt/homebrew/bin/gh pr merge 12", ("12",)),
        ("sudo -u me gh pr merge 12", ("12",)),
        ('bash -c "gh pr merge 12"', ("12",)),
        ("sh -c 'npm test && gh pr merge 12 --merge'", ("12", "--merge")),
        ('zsh -lc "/opt/homebrew/bin/gh pr merge 12"', ("12",)),
    ],
)
def test_find_command_finds_real_invocations(command: str, expected: tuple[str, ...]) -> None:
    assert hooklib.find_command(command, MERGE) == expected


@pytest.mark.parametrize(
    "command",
    [
        'gh issue create --body "다 되면 gh pr merge 로 올린다"',
        "grep -n 'gh pr merge' hooks/*.py",
        "echo gh pr merge 12",
        "cat > body.md <<'EOF'\n머지는\ngh pr merge 12\nEOF\ngh issue create --body-file body.md",
        "npm test # 그다음 gh pr merge 12",
        '/opt/homebrew/bin/gh issue create --body "gh pr merge 12"',
        "env echo gh pr merge 12",
        'bash -c "echo gh pr merge 12"',
        "bash script.sh gh pr merge 12",
    ],
)
def test_find_command_ignores_text_inside_other_commands(command: str) -> None:
    assert hooklib.find_command(command, MERGE) is None


@pytest.mark.parametrize(
    ("command", "sub", "expected"),
    [
        ("git push -u origin feat_1", "push", ("-u", "origin", "feat_1")),
        ("/usr/bin/git -C /tmp/wt push origin litellm_airgap", "push", ("origin", "litellm_airgap")),
        ("git -c user.name=x --no-pager push origin main", "push", ("origin", "main")),
        ("env GIT_TRACE=1 command git push", "push", ()),
        ('bash -c "git push origin main"', "push", ("origin", "main")),
        ('git add -A && git commit -m "x"', "commit", ("-m", "x")),
        ('git -C /tmp/wt commit -q -m "x"', "commit", ("-q", "-m", "x")),
    ],
)
def test_find_git_subcommand(command: str, sub: str, expected: tuple[str, ...]) -> None:
    assert hooklib.find_git_subcommand(command, sub) == expected


@pytest.mark.parametrize(
    ("command", "sub"),
    [
        ('gh issue create --body "git push origin main 하고 git commit"', "push"),
        ('gh issue create --body "git commit 전에 심사"', "commit"),
        ("cat > a.md <<'EOF'\ngit commit -m x\nEOF", "commit"),
        ("git log --grep commit", "commit"),
        ("git status", "push"),
    ],
)
def test_find_git_subcommand_ignores_non_invocations(command: str, sub: str) -> None:
    assert hooklib.find_git_subcommand(command, sub) is None


@pytest.mark.parametrize(
    ("args", "current"),
    [
        (("origin", "main"), "feat_2_x"),
        (("origin", "litellm_airgap"), "feat_2_x"),
        (("origin", "+feat:refs/heads/litellm_airgap"), "feat_2_x"),
        (("origin",), "litellm_airgap"),
        ((), "main"),
        (("origin", "HEAD"), "litellm_airgap"),
        (("-o", "ci.skip", "origin", "main"), "feat_2_x"),
    ],
)
def test_push_to_protected_branch_is_blocked(args: tuple[str, ...], current: str) -> None:
    verdict: Final = hooklib.protected_push_verdict(args, current)
    assert not verdict.ok
    assert "PR" in verdict.reason


@pytest.mark.parametrize(
    ("args", "current"),
    [
        (("-u", "origin", "feat_2_x"), "feat_2_x"),
        (("origin",), "feat_2_x"),
        (("origin", "HEAD"), "fix_3_y"),
        (("-o", "main", "origin", "feat_2_x"), "feat_2_x"),
    ],
)
def test_push_to_work_branch_is_allowed(args: tuple[str, ...], current: str) -> None:
    assert hooklib.protected_push_verdict(args, current).ok


def _run(
    name: str, status: str, conclusion: str = "", started: str = "2026-11-08T10:00:00Z", workflow: str = "airgap CI"
) -> dict[str, str]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started,
        "workflowName": workflow,
    }


def test_ci_ignores_runs_of_other_workflows() -> None:
    upstream: Final = _run("Conventional PR Title", "COMPLETED", "CANCELLED", workflow="Conventional PR Title")
    assert hooklib.ci_verdict("litellm_airgap", [upstream, _run("unit", "COMPLETED", "SUCCESS")]).ok
    assert not hooklib.ci_verdict("litellm_airgap", [upstream]).ok


def test_ci_all_green_passes_and_skipped_or_neutral_are_not_failures() -> None:
    checks: Final = [
        _run("a", "COMPLETED", "SUCCESS"),
        _run("b", "COMPLETED", "SKIPPED"),
        _run("c", "COMPLETED", "NEUTRAL"),
    ]
    assert hooklib.ci_verdict("litellm_airgap", checks).ok


@pytest.mark.parametrize("conclusion", ["FAILURE", "CANCELLED", "TIMED_OUT"])
def test_ci_failure_names_the_check(conclusion: str) -> None:
    verdict: Final = hooklib.ci_verdict(
        "litellm_airgap", [_run("ok", "COMPLETED", "SUCCESS"), _run("lint", "COMPLETED", conclusion)]
    )
    assert not verdict.ok
    assert "lint" in verdict.reason
    assert "실패" in verdict.reason


def test_ci_still_running_blocks_until_done() -> None:
    verdict: Final = hooklib.ci_verdict("litellm_airgap", [_run("unit", "IN_PROGRESS")])
    assert not verdict.ok
    assert "unit" in verdict.reason
    assert "끝난 뒤" in verdict.reason


@pytest.mark.parametrize("checks", [[], None])
def test_ci_with_no_checks_on_a_ci_base_has_not_started(checks: list[dict[str, str]] | None) -> None:
    assert not hooklib.ci_verdict("litellm_airgap", checks).ok


def test_ci_is_not_required_for_bases_without_ci() -> None:
    assert hooklib.ci_verdict("feat_1_x", []).ok


def test_ci_judges_the_latest_rerun_of_a_check() -> None:
    old: Final = _run("a", "COMPLETED", "FAILURE", "2026-11-08T10:00:00Z")
    again: Final = _run("a", "COMPLETED", "SUCCESS", "2026-11-08T11:00:00Z")
    assert hooklib.ci_verdict("litellm_airgap", [again, old]).ok
    assert hooklib.ci_verdict("litellm_airgap", [old, again]).ok


def test_ci_reads_legacy_status_contexts() -> None:
    def status(state: str) -> list[dict[str, str]]:
        return [{"__typename": "StatusContext", "context": "ext", "state": state}]

    assert not hooklib.ci_verdict("litellm_airgap", status("PENDING")).ok
    assert "ext" in hooklib.ci_verdict("litellm_airgap", status("ERROR")).reason
    assert hooklib.ci_verdict("litellm_airgap", status("SUCCESS")).ok


def test_freshness_requires_the_latest_base_only_on_ci_bases() -> None:
    assert not hooklib.freshness_verdict("litellm_airgap", False).ok
    assert "rebase" in hooklib.freshness_verdict("litellm_airgap", False).reason
    assert hooklib.freshness_verdict("litellm_airgap", True).ok
    assert hooklib.freshness_verdict("feat_1_x", False).ok


def _hook(script: str, command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    payload: Final = json.dumps({"tool_input": {"command": command}, "cwd": str(cwd)})
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)], input=payload, capture_output=True, text=True, check=False
    )


def test_hook_blocks_instead_of_crashing_open(tmp_path: Path) -> None:
    result: Final = _hook("block_protected_push.py", "git push origin feat_1", tmp_path)
    assert result.returncode == 2
    assert "오류" in result.stderr


def test_hook_ignores_unrelated_commands(tmp_path: Path) -> None:
    assert _hook("block_protected_push.py", "ls -la", tmp_path).returncode == 0
