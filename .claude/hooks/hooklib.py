"""Shared logic for the Claude Code hooks. Stdlib only and Python 3.9 compatible, since hooks run with system python3

Every verdict is a pure function so tests/airgap/test_hooklib.py can pin its behavior
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Final, NoReturn

PROTECTED_BRANCHES: Final = frozenset({"main", "litellm_airgap"})
CI_BASES: Final = frozenset({"litellm_airgap"})
CI_WORKFLOW: Final = "airgap CI"

_PATH_ARG: Final = r"""(?:"([^"]*)"|'([^']*)'|([^\s;&|]+))"""
_LEADING_CD: Final = re.compile(r"^\s*cd\s+" + _PATH_ARG + r"\s*(?:&&|;)")
_LEADING_EXPORT: Final = re.compile(r"^\s*export\s+[^;&|]*(?:&&|;)")
_GIT_DASH_C: Final = re.compile(r"\bgit\s+-C\s+" + _PATH_ARG)
_ENV_ASSIGN: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC_TAG: Final = re.compile(r"""^(?:'([^']*)'|"([^"]*)"|([^\s;&|<>()]+))""")
_PASS_THROUGH: Final = frozenset(
    {"command", "exec", "builtin", "nohup", "time", "sudo", "env", "timeout", "nice", "xargs", "caffeinate"}
)
_SHELL_KEYWORDS: Final = frozenset(
    {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "time"}
)
_SUBSTITUTION: Final = re.compile(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)|`([^`]*)`")
_SHELLS: Final = frozenset({"sh", "bash", "zsh", "dash"})
_GIT_VALUE_OPTIONS: Final = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)
_PASSED: Final = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})

if TYPE_CHECKING:
    from typing import TypeAlias

    Words: TypeAlias = tuple[str, ...]


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""


OK: Final = Verdict(True)


def _first_group(match: re.Match[str]) -> str:
    return next(group for group in match.groups() if group is not None)


def leading_dir(command: str, cwd: str) -> str:
    """Folder after the leading `cd X &&` chain (skipping `export ...;`)"""
    directory = cwd  # rebind-ok: follows each leading cd in turn
    rest = command  # rebind-ok: consumes the command prefix
    while True:
        cd = _LEADING_CD.match(rest)
        if cd:
            directory = os.path.normpath(os.path.join(directory, _first_group(cd)))
            rest = rest[cd.end() :]
            continue
        exported = _LEADING_EXPORT.match(rest)
        if not exported:
            return directory
        rest = rest[exported.end() :]


def leading_cd_count(command: str) -> int:
    count = 0  # rebind-ok: counts the leading cd chain
    rest = command  # rebind-ok: consumes the command prefix
    while True:
        cd = _LEADING_CD.match(rest) or _LEADING_EXPORT.match(rest)
        if not cd:
            return count
        count += 1 if rest.lstrip().startswith("cd") else 0
        rest = rest[cd.end() :]


def command_dir(command: str, cwd: str) -> str:
    """Folder the command actually runs in: follows leading `cd X &&` (skipping `export ...;`) and `git -C X`"""
    directory: Final = leading_dir(command, cwd)
    git_c: Final = _GIT_DASH_C.search(command)
    return os.path.normpath(os.path.join(directory, _first_group(git_c))) if git_c else directory


def has_unfollowed_cd(command: str) -> bool:
    """A `cd` the hooks cannot follow, e.g. mid-line or inside a subshell, so the working folder is unknown"""
    cds: Final = sum(1 for words in commands_in(command) if words[0] in ("cd", "pushd", "popd"))
    return cds > leading_cd_count(command)


class _Splitter:
    """Splits a shell line into simple commands. Quotes, heredoc bodies and comments are not commands"""

    def __init__(self, command: str) -> None:
        self.command = command
        self.commands: list[Words] = []  # mutable-ok: shell lexing is inherently stateful
        self.words: list[str] = []  # mutable-ok: shell lexing is inherently stateful
        self.word = ""
        self.in_word = False
        self.heredocs: list[tuple[str, bool]] = []  # mutable-ok: shell lexing is inherently stateful

    def end_word(self) -> None:
        if self.in_word:
            self.words.append(self.word)
        self.word = ""
        self.in_word = False

    def end_command(self) -> None:
        self.end_word()
        words: Final = self.words
        start: Final = next((i for i, w in enumerate(words) if not _ENV_ASSIGN.match(w)), len(words))
        if words[start:]:
            self.commands.append(tuple(words[start:]))
        self.words = []

    def skip_heredocs(self, newline_at: int) -> int:
        at = newline_at + 1  # rebind-ok: walks heredoc body lines
        for end, strip in self.heredocs:
            while True:
                nxt = self.command.find("\n", at)
                line = self.command[at : len(self.command) if nxt == -1 else nxt]
                at = len(self.command) if nxt == -1 else nxt + 1
                if (line.lstrip("\t") if strip else line) == end or nxt == -1:
                    break
        self.heredocs = []
        return at - 1

    def split(self) -> tuple[Words, ...]:
        command: Final = self.command
        i = 0  # rebind-ok: lexer cursor
        while i < len(command):
            c = command[i]
            if c == "\\" and i + 1 < len(command):
                if command[i + 1] != "\n":
                    self.word += command[i + 1]
                    self.in_word = True
                i += 1
            elif c == "'":
                end = command.find("'", i + 1)
                self.word += command[i + 1 : len(command) if end == -1 else end]
                self.in_word = True
                i = len(command) if end == -1 else end
            elif c == "`":
                end = command.find("`", i + 1)
                stop = len(command) if end == -1 else end + 1
                self.word += command[i:stop]
                self.in_word = True
                i = stop - 1
            elif c == '"':
                j = i + 1
                while j < len(command) and command[j] != '"':
                    if command[j] == "\\" and j + 1 < len(command):
                        j += 1
                    self.word += command[j]
                    j += 1
                self.in_word = True
                i = j
            elif c == "#" and not self.in_word:
                end = command.find("\n", i)
                i = (len(command) if end == -1 else end) - 1
            elif c == "<" and command[i + 1 : i + 2] == "<" and command[i + 2 : i + 3] != "<":
                self.end_word()
                j = i + 2
                strip = command[j : j + 1] == "-"
                if strip:
                    j += 1
                while command[j : j + 1] in (" ", "\t") and j < len(command):
                    j += 1
                tag = _HEREDOC_TAG.match(command[j:])
                if tag:
                    self.heredocs.append((_first_group(tag), strip))
                    j += tag.end()
                i = j - 1
            elif c == "\n":
                self.end_command()
                i = self.skip_heredocs(i)
            elif c in ";&|()":
                self.end_command()
            elif c in " \t":
                self.end_word()
            else:
                self.word += c
                self.in_word = True
            i += 1
        self.end_command()
        return tuple(self.commands)


def simple_commands(command: str) -> tuple[Words, ...]:
    return _Splitter(command).split()


def _base_name(word: str) -> str:
    return re.split(r"[/\\]", word)[-1]


def _skip_wrapper_options(name: str, rest: Words) -> Words:
    """Drops a wrapper's own options (and their values) so the wrapped program comes first"""
    if name == "timeout" and rest and not rest[0].startswith("-"):
        return rest[1:]
    if not rest or not rest[0].startswith("-"):
        return rest
    takes_value: Final = (
        (name == "sudo" and re.fullmatch(r"-[ugCDhpr]", rest[0]))
        or (name == "env" and re.fullmatch(r"-[uSC]", rest[0]))
        or (name == "timeout" and re.fullmatch(r"-[sk]", rest[0]))
        or (name == "nice" and rest[0] == "-n")
        or (name == "xargs" and re.fullmatch(r"-[IinLlPdaEs]", rest[0]))
    )
    return _skip_wrapper_options(name, rest[2:] if takes_value else rest[1:])


def _invocations(words: Words, depth: int = 0) -> tuple[Words, ...]:
    """Unwraps wrappers (`env`, `sudo`, `timeout`, `xargs` ...), shell keywords, paths on the program,
    `bash -c "..."` and `eval` bodies, and `$(...)` or backtick substitutions inside any word"""
    if depth > 5:
        return ()
    start: Final = next(
        (i for i, w in enumerate(words) if not _ENV_ASSIGN.match(w) and w not in _SHELL_KEYWORDS), len(words)
    )
    rest: Final = tuple(words[start:])
    if not rest:
        return ()
    matches: Final = chain.from_iterable(map(_SUBSTITUTION.finditer, rest))
    substituted: Final = tuple(chain.from_iterable(_parse(m.group(1) or m.group(2) or "", depth + 1) for m in matches))
    name: Final = _base_name(rest[0])
    if name in _PASS_THROUGH:
        return substituted + _invocations(_skip_wrapper_options(name, rest[1:]), depth + 1)
    if name == "eval":
        return substituted + _parse(" ".join(rest[1:]), depth + 1)
    if name in _SHELLS:
        at: Final = next((i for i, w in enumerate(rest) if i > 0 and re.fullmatch(r"-[a-z]*c[a-z]*", w)), -1)
        if at != -1 and at + 1 < len(rest):
            return substituted + _parse(rest[at + 1], depth + 1)
    return substituted + ((name, *rest[1:]),)


def _parse(command: str, depth: int) -> tuple[Words, ...]:
    return tuple(chain.from_iterable(_invocations(words, depth) for words in simple_commands(command)))


def commands_in(command: str) -> tuple[Words, ...]:
    return _parse(command, 0)


def all_commands(command: str, name: Sequence[str]) -> tuple[Words, ...]:
    """Remaining words of every real `name ...` invocation, ignoring text inside other commands' arguments"""
    return tuple(words[len(name) :] for words in commands_in(command) if words[: len(name)] == tuple(name))


def find_command(command: str, name: Sequence[str]) -> Words | None:
    found: Final = all_commands(command, name)
    return found[0] if found else None


def _git_subcommand_index(words: Words, index: int = 1) -> int:
    if index >= len(words) or not words[index].startswith("-"):
        return index
    return _git_subcommand_index(words, index + (2 if words[index] in _GIT_VALUE_OPTIONS else 1))


@dataclass(frozen=True)
class GitCall:
    args: Words
    dash_c: str | None


def _dash_c(words: Words, end: int) -> str | None:
    values: Final = [words[i + 1] for i in range(1, end) if words[i] == "-C" and i + 1 < end]
    return values[-1] if values else None


def git_calls(command: str, sub: str) -> tuple[GitCall, ...]:
    """Every real `git [global options] <sub> ...` invocation with its own `-C` folder"""
    gits: Final = (words for words in commands_in(command) if words[0] == "git")
    found: Final = ((words, _git_subcommand_index(words)) for words in gits)
    return tuple(
        GitCall(words[index + 1 :], _dash_c(words, index))
        for words, index in found
        if words[index : index + 1] == (sub,)
    )


def find_git_subcommand(command: str, sub: str) -> Words | None:
    calls: Final = git_calls(command, sub)
    return calls[0].args if calls else None


_PUSH_VALUE_FLAGS: Final = frozenset({"-o", "--push-option", "--repo", "--receive-pack", "--exec"})
_PUSH_EVERYTHING: Final = frozenset({"--all", "--mirror", "--branches"})


def _refspecs(args: Words) -> Words:
    positional: Final = tuple(
        a
        for i, a in enumerate(args)
        if a and not a.startswith("-") and (i == 0 or args[i - 1] not in _PUSH_VALUE_FLAGS)
    )
    return positional[1:]


def push_targets(args: Words, current_branch: str) -> frozenset[str]:
    refspecs: Final = _refspecs(args)
    targets: Final = frozenset(re.sub(r"^refs/heads/", "", r.lstrip("+").split(":")[-1]) for r in refspecs)
    if not refspecs or "HEAD" in targets:
        return targets | {current_branch}
    return targets


def protected_push_verdict(args: Words, current_branch: str | None) -> Verdict:
    """current_branch is None when the hook cannot tell which folder the push runs in"""
    if _PUSH_EVERYTHING & set(args):
        return Verdict(
            False, "--all·--mirror push 는 main·litellm_airgap 까지 올리므로 막습니다. 브랜치를 하나씩 push 해 주세요"
        )
    refspecs: Final = _refspecs(args)
    if any("$" in r or "{" in r or "`" in r for r in refspecs):
        return Verdict(
            False, "push 대상에 변수가 있어 어느 브랜치인지 알 수 없습니다. 브랜치 이름을 그대로 적어 주세요"
        )
    if current_branch is None and (not refspecs or any(r.split(":")[-1] == "HEAD" for r in refspecs)):
        return Verdict(
            False, "훅이 따라갈 수 없는 cd 가 있어 지금 브랜치를 알 수 없습니다. push 할 브랜치 이름을 적어 주세요"
        )
    hit: Final = sorted(push_targets(args, current_branch or "") & PROTECTED_BRANCHES)
    if not hit:
        return OK
    return Verdict(
        False,
        f"{hit[0]} 에 바로 push 할 수 없습니다. 브랜치를 만들어 PR 로 올려 주세요 (.claude/rules/workflow.md 5번)",
    )


def push_command_verdict(command: str, branch_for: Callable[[str | None], str]) -> Verdict:
    """Judges every push in the command line. branch_for maps a push's `-C` folder (or None) to its current branch"""
    unknown_folder: Final = has_unfollowed_cd(command)
    verdicts: Final = (
        protected_push_verdict(call.args, None if unknown_folder else branch_for(call.dash_c))
        for call in git_calls(command, "push")
    )
    return next((v for v in verdicts if not v.ok), OK)


@dataclass(frozen=True)
class _Check:
    name: str
    done: bool
    passed: bool
    started_at: str


def _check_state(item: Mapping[str, object]) -> _Check:
    raw_start: Final = str(item.get("startedAt") or "")
    started: Final = raw_start if raw_start and not raw_start.startswith("0001") else "~not-started"
    if item.get("__typename") == "StatusContext" or ("state" in item and "status" not in item):
        state: Final = str(item.get("state") or "").upper()
        return _Check(
            str(item.get("context") or "(이름 없음)"), state not in ("PENDING", "EXPECTED"), state == "SUCCESS", started
        )
    done: Final = str(item.get("status") or "").upper() == "COMPLETED"
    passed: Final = done and str(item.get("conclusion") or "").upper() in _PASSED
    return _Check(str(item.get("name") or "(이름 없음)"), done, passed, started)


def merge_base_verdict(base: str) -> Verdict:
    if base in CI_BASES:
        return OK
    return Verdict(
        False, f"PR 대상이 {base} 입니다. fork 작업은 litellm_airgap 으로만 머지합니다 (.claude/rules/workflow.md 3번)"
    )


def ci_verdict(base: str, checks: Iterable[Mapping[str, object]] | None) -> Verdict:
    """Mergeable only when the latest run of every airgap CI check finished green. Disabled upstream workflows may
    still leave cancelled runs on the PR, so checks from other workflows are ignored"""
    if base not in CI_BASES:
        return OK
    ours: Final = (item for item in checks or () if item.get("workflowName") == CI_WORKFLOW)
    states: Final = sorted(map(_check_state, ours), key=lambda c: c.started_at)
    latest: Final = tuple({c.name: c for c in states}.values())
    if not latest:
        return Verdict(False, "PR 의 airgap CI 검사가 아직 시작되지 않았습니다. CI 가 끝난 뒤 머지해 주세요")
    failed: Final = [c.name for c in latest if c.done and not c.passed]
    if failed:
        return Verdict(False, f"PR 의 CI 검사가 실패했습니다: {', '.join(failed)}. 고친 뒤 다시 머지해 주세요")
    running: Final = [c.name for c in latest if not c.done]
    if running:
        return Verdict(False, f"PR 의 CI 검사가 아직 돌고 있습니다: {', '.join(running)}. CI 가 끝난 뒤 머지해 주세요")
    return OK


def freshness_verdict(base: str, contains_base: bool) -> Verdict:
    if base not in CI_BASES or contains_base:
        return OK
    return Verdict(
        False,
        f"PR 브랜치가 {base} 의 최신 커밋을 품고 있지 않습니다. {base} 위로 rebase 하고 push 한 뒤, "
        "CI 가 다시 초록이 되면 머지해 주세요. 합친 코드를 검사한 뒤에 머지하기 위해서입니다",
    )


def run_hook(check: Callable[[str, str], None], follow_git_dash_c: bool = True) -> None:
    """Runs a hook check and blocks on any crash, so a broken hook never lets the command through"""
    try:
        data: Final = json.load(sys.stdin)
        command: Final = str((data.get("tool_input") or {}).get("command") or "")
        cwd: Final = str(data.get("cwd") or os.getcwd())
        check(command, command_dir(command, cwd) if follow_git_dash_c else cwd)
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001  # fail closed on anything unexpected
        block(f"훅 검사({sys.argv[0]}) 중 오류가 나서 명령을 막았습니다: {error!r}")


def block(reason: str) -> NoReturn:
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def git(cwd: str, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    ).stdout
