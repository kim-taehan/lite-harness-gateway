"""Before `gh pr merge`: same code as the PR, branch holds the latest base, PR CI green, local checks exit 0

.claude/rules/workflow.md 4번
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Final

from hooklib import CI_BASES, block, ci_verdict, find_command, freshness_verdict, git, run_hook

GH_CANDIDATES: Final = ("gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh")
VALUE_FLAGS: Final = frozenset(
    {
        "-R",
        "--repo",
        "-b",
        "--body",
        "-F",
        "--body-file",
        "-t",
        "--subject",
        "-A",
        "--author-email",
        "--match-head-commit",
    }
)


def gh_binary() -> str | None:
    return next((found for found in map(shutil.which, GH_CANDIDATES) if found), None)


def gh_env(gh: str, cwd: str) -> dict[str, str]:
    """Uses the repo owner's gh login when one exists, since the active gh account may be a different one"""
    remote: Final = git(cwd, "remote", "get-url", "origin").strip()
    owner: Final = remote.rstrip("/").removesuffix(".git").replace(":", "/").split("/")[-2]
    token: Final = subprocess.run(
        [gh, "auth", "token", "-u", owner], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    if token.returncode != 0 or not token.stdout.strip():
        return dict(os.environ)
    return {**os.environ, "GH_TOKEN": token.stdout.strip()}


def check(command: str, cwd: str) -> None:
    args: Final = find_command(command, ("gh", "pr", "merge"))
    if args is None:
        return
    gh: Final = gh_binary()
    if gh is None:
        block(
            "PR 과 CI 결과를 확인할 gh 를 찾지 못해 머지를 막았습니다. GitHub CLI(gh)를 설치하거나 PATH 에 두어 주세요"
        )
    pr_arg: Final = next(
        (a for i, a in enumerate(args) if a and not a.startswith("-") and (i == 0 or args[i - 1] not in VALUE_FLAGS)),
        None,
    )
    repo_at: Final = next((i for i, a in enumerate(args) if a in ("-R", "--repo")), -1)
    repo: Final = ("-R", args[repo_at + 1]) if 0 <= repo_at < len(args) - 1 else ()
    view: Final = subprocess.run(
        [
            gh,
            "pr",
            "view",
            *((pr_arg,) if pr_arg else ()),
            *repo,
            "--json",
            "headRefName,headRefOid,baseRefName,statusCheckRollup",
        ],
        cwd=cwd,
        env=gh_env(gh, cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if view.returncode != 0:
        block("머지할 PR 을 찾지 못했습니다. PR 번호와 gh 로그인 계정을 확인해 주세요")
    pr: Final = json.loads(view.stdout)
    base: Final = str(pr.get("baseRefName") or "")

    current: Final = git(cwd, "branch", "--show-current").strip()
    if pr.get("headRefName") != current:
        block(
            f"지금 폴더의 브랜치({current})가 PR 브랜치({pr.get('headRefName')})와 다릅니다. PR 브랜치를 체크아웃한 폴더에서 머지해 주세요. 그 코드로 검사합니다"
        )
    dirty: Final = git(cwd, "status", "--porcelain", "--untracked-files=no").strip()
    if dirty:
        block(
            f"커밋하지 않은 수정이 있습니다. 커밋하고 push 한 뒤 머지해 주세요. 그래야 검사한 코드가 PR 코드와 같습니다\n{dirty[:500]}"
        )
    local: Final = git(cwd, "rev-parse", "HEAD").strip()
    if pr.get("headRefOid") and local != pr["headRefOid"]:
        block(
            f"지금 폴더의 커밋({local[:7]})이 PR 에 올라간 커밋({str(pr['headRefOid'])[:7]})과 다릅니다. push 하거나 pull 해서 맞춘 뒤 머지해 주세요"
        )

    if base in CI_BASES:
        try:
            git(cwd, "fetch", "-q", "origin", f"+refs/heads/{base}:refs/remotes/origin/{base}")
        except subprocess.CalledProcessError:
            block(
                f"origin/{base} 를 받아 오지 못해 PR 브랜치가 최신인지 확인할 수 없습니다. 네트워크를 확인한 뒤 다시 머지해 주세요"
            )
    contains_base: Final = (
        base not in CI_BASES
        or subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{base}", "HEAD"], cwd=cwd).returncode == 0
    )
    fresh: Final = freshness_verdict(base, contains_base)
    if not fresh.ok:
        block(fresh.reason)
    ci: Final = ci_verdict(base, pr.get("statusCheckRollup"))
    if not ci.ok:
        block(ci.reason)

    check: Final = subprocess.run(
        ["sh", "scripts/airgap_check.sh"], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
    )
    if check.returncode != 0:
        block(
            f"scripts/airgap_check.sh 가 종료 코드 {check.returncode} 로 실패해서 머지를 막았습니다. 고친 뒤 다시 머지해 주세요\n{check.stderr[-2000:]}"
        )


run_hook(check)
