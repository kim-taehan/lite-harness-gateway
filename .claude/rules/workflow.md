# 작업 흐름

괄호 안에 훅·CI 가 적힌 것만 자동으로 막는다. 나머지는 커밋 심사(`/convention-review`)와 사람이 지킨다
이 저장소는 litellm fork 다. 루트의 `AGENTS.md` 는 upstream 의 규칙이라 코드 규약은 그대로 따르지만, 브랜치·PR·커밋·언어처럼 흐름에 관한 것은 이 파일이 앞선다

1. 모든 작업은 GitHub 이슈부터 만든다. 이슈 없이는 브랜치도 수정도 없다
2. 브랜치는 `litellm_airgap` 에서 만든다. 이름은 `feat_<이슈>_<짧은_snake>` · `fix_<이슈>_…` · `refactor_<이슈>_…` · `docs_<이슈>_…`. `main` 은 upstream litellm 을 그대로 따라가는 브랜치라 작업 기준으로 쓰지 않는다
3. PR 은 `litellm_airgap` 으로 보낸다. PR 과 커밋 제목은 쉬운 한국어로 `<무엇을 왜> (#<이슈>)`, 예: `SSO 로그인 뒤 팀이 비어 보이던 문제 수정 (#12)`. 본문에 `Closes #<이슈>` 를 쓴다
4. 머지 조건은 `scripts/airgap_check.sh` 의 **종료 코드가 0** 이고, **PR 의 CI 검사가 모두 초록**이고, PR 브랜치가 `litellm_airgap` 의 최신 커밋을 품은 것이다. 출력을 grep 한 결과로 판단하지 않는다. upstream 린트 게이트(`make lint`)는 무거워서 CI 에서만 돈다. 뒤처졌으면 rebase·push 하고 CI 를 다시 기다린다. (`gh pr merge` 앞에서 훅이 확인한다, `.claude/hooks/check_before_merge.py`)
   GitHub 웹의 Merge 버튼은 쓰지 않는다. 브랜치 보호를 쓰지 않아서 GitHub 은 CI 가 실패해도 머지를 막지 않는다
5. `main`·`litellm_airgap` 에 바로 push 하지 않는다. 늘 브랜치에서 PR 로 간다. (Claude Code 에서는 훅이 막는다, `.claude/hooks/block_protected_push.py`. 사람이 직접 하는 push 는 스스로 지킨다)
6. 한 번에 요청받은 것만 한다. 하다가 발견한 다른 것은 "다음 할 일" 로 적어 두기만 한다
7. 간단한 수정과 오류는 이슈를 만들고 바로 처리한 뒤 보고한다
8. 실물 테스트(`docker-dev/` 의 Keycloak·Ollama, `tests/e2e/`)는 필요할 때만 돌린다. 단위 테스트는 가짜 의존으로 쓴다
9. 이슈·PR·머지 코멘트는 비개발자도 읽을 수 있게 쉽게 쓴다. 무엇이 왜 바뀌는지를 먼저 쓰고, 코드·파일 이름은 꼭 필요할 때만. 사람을 경력 수준으로 가르는 말 대신 "새 팀원" 으로 쓴다
10. 커밋 전에 `/convention-review` 로 변경을 이 규칙들과 대조한다. (훅이 심사 없는 커밋을 막는다, `.claude/hooks/require_convention_review.py`)
11. 규칙을 더하거나 바꾸면 fork 코드 전체에 소급해 위반을 센다. 기계로 잴 수 있으면 `tests/airgap/` 에 검사를 붙이고 [필수] 규칙 줄 끝에 검사 위치를 적는다(못 재면 `— 커밋 심사`). 기존 위반이 있으면 기준선(`tests/airgap/baseline/`)으로 고정하고 새로 생기는 것만 막는다. 기준선은 늘어도, 줄었는데 그대로여도 실패한다. 갱신은 `UPDATE_AIRGAP_BASELINE=1 .venv/bin/python -m pytest tests/airgap`. (`/convention-review` 가 확인한다)
12. 크기가 M·L 이거나 핵심 흐름(추론 경로, 인증·SSO, 키·팀·예산, 사용량 회계, 마이그레이션)에 닿는 PR 은 머지 전에 `reviewer` 에이전트(`.claude/agents/reviewer.md`)에게 PR 번호를 주고, 남긴 지적을 처리하거나 처리하지 않는 이유를 PR 에 적는다. 작업은 `worker` 에이전트(`.claude/agents/worker.md`)가 이 흐름을 따른다
13. upstream 동기화는 GitHub 의 Sync fork 로 `main` 을 올린 뒤, `litellm_airgap` 에서 `sync_<YYYYMMDD>` 브랜치를 만들어 `origin/main` 을 머지하고 PR 로 올린다. 동기화 뒤에는 `scripts/airgap_disable_upstream_workflows.sh` 를 돌려 새로 들어온 upstream 워크플로를 끈다
