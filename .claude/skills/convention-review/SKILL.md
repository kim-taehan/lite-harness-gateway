---
name: convention-review
description: "커밋 전에 바뀐 내용(git diff --cached + git diff + 새 파일)을 .claude/rules 의 팀 규칙과 대조해 위반을 보고하고, 위반이 없으면 심사 상태를 기록한다. 커밋 훅이 '규칙 심사가 필요합니다' 라며 막았을 때, 또는 커밋 전에 규칙을 점검하고 싶을 때 (/convention-review)."
---

# convention-review, 팀 규칙 기반 커밋 심사

커밋 훅(`.claude/hooks/require_convention_review.py`)은 이 스킬의 마지막 단계가 기록한 상태와
지금 변경이 같을 때만 커밋을 통과시킨다. **4단계 상태 저장까지 끝까지 한다.**

## 절차

1. **규칙 읽기**: `.claude/rules/` 의 마크다운을 전부 읽는다. 새로 생긴 규칙 파일도 자동으로 대상이다. 코드를 바꿨으면 루트 `AGENTS.md` 의 코딩 규약도 대조 대상이다
2. **심사 범위**: `git diff --cached`(스테이징) + `git diff`(미스테이징) + `git ls-files --others --exclude-standard`(새 파일). 모두 비면 `git show HEAD` 를 대신 심사한다
3. **대조와 보고**: 변경을 규칙 하나하나와 대조한다. 위반마다 규칙(파일·번호), 파일, 줄을 적는다. 없으면 "위반 없음"
   - 위반이 있으면 먼저 고치고 2단계부터 다시 한다. 위반을 남긴 채 4단계로 가지 않는다
   - **[검토]** 규칙은 위반이 아니라 확인 질문으로만 남긴다. **[필수]** 는 위반이다
   - 줄 끝에 `— tests/…` 가 붙은 규칙은 `scripts/airgap_check.sh` 가 자동으로 잰다. 바뀐 코드가 그 범위에 닿으면 `.venv/bin/python -m pytest tests/airgap -q` 를 돌려 종료 코드로 확인한다
   - 심사는 `— 커밋 심사` 로 적힌 규칙에 힘을 쓴다. 특히 반드시 볼 것:
     - 키·토큰·비밀번호가 API 응답, 에러 메시지, 예외 문자열에 들어가는지(code-quality 4번)
     - OpenAI 호환 추론 API 의 요청·응답 모양이 바뀌는지(architecture 6번)
     - upstream 파일에 등록 몇 줄 이상을 넣고 있는지(architecture 1번). 기준선이 늘었다면 새 모듈로 뺄 수 없는지 먼저 따진다
   - 커밋·PR 제목이 workflow 3번 형식(쉬운 한국어, `(#이슈)`)인지 본다
3-1. **규칙이 바뀐 변경이면 소급 검사**(workflow 11번): 변경에 `.claude/rules/` 가 들어 있으면, 더하거나 바뀐 규칙마다
   - fork 코드 전체에서 위반을 세어 보고한다(바뀐 줄만 보지 않는다). fork 코드 목록은 `.venv/bin/python -m tests.airgap.fork_diff python-sources`
   - 기계로 잴 수 있는데 `tests/airgap/` 검사가 없으면 위반이다. 검사를 붙이고, 기존 위반이 있으면 기준선(`tests/airgap/baseline/`)으로 고정한다
   - [필수] 규칙 줄 끝에 검사 위치(`— tests/…` 또는 `— 커밋 심사`)가 없으면 위반이다(`tests/airgap/test_fork_rules.py` 도 잰다)
4. **상태 저장(필수, 마지막)**:
   ```sh
   python3 .claude/hooks/convention_state.py store
   ```
   "스테이징 diff + 워크트리 diff + 새 파일 + 규칙 파일" 지문을 git 폴더(`git rev-parse --git-path airgap-convention-state`)에 적는다. worktree 마다 따로 있고 커밋되지 않는다. 이후 변경이나 규칙이 바뀌면 다시 심사해야 한다
