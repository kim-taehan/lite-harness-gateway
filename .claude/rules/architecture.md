# 구조 규칙

**[필수]** 는 지켜야 하고, **[검토]** 는 어기면 PR 에 이유를 적는다(심사는 확인 질문으로만 남긴다)
[필수] 줄 끝의 `— tests/…` 는 그 규칙을 자동으로 막는 검사, `— 커밋 심사` 는 자동 검사가 없어 `/convention-review` 와 사람이 지키는 것이다
"fork 코드" 는 `origin/main`(upstream) 과의 merge-base 대비 이 저장소가 더하거나 바꾼 것이다(`tests/airgap/fork_diff.py`)

## upstream 과의 경계
1. **[필수]** 새 기능은 새 파일(모듈)에 만들고, upstream 파일에는 등록·호출 몇 줄만 더한다. upstream 파일을 고친 줄 수는 파일별 기준선으로 고정한다. upstream 동기화 때마다 충돌을 손으로 풀어야 하는 양이 이 숫자다. — `tests/airgap/test_fork_rules.py`
2. **[필수]** fork 의 테스트도 새 테스트 파일에 둔다. upstream 테스트 파일에 이어 붙이지 않는다(1번 기준선이 같이 센다). — `tests/airgap/test_fork_rules.py`
3. **[검토]** upstream 기능을 끄거나 숨길 때는 코드를 지우지 말고 설정이나 경로 목록(`gateway/routes/`, `backend/routes/` 의 allowlist)으로 한다
4. **[필수]** `AGENTS.md`, upstream 워크플로, upstream 린트 게이트(`scripts/*_gate.py`)는 고치지 않는다. fork 전용 규칙은 `.claude/rules/`, 검사는 `tests/airgap/`, CI 는 `.github/workflows/airgap-ci.yml` 에 둔다. — `tests/airgap/test_fork_rules.py`

## 바깥과의 경계
5. **[필수]** 런타임 코드에 폐쇄망 밖 주소를 새로 넣지 않는다. 허용은 localhost·127.x·`host.docker.internal`·`.internal`·`.local`·`.svc` 같은 내부 이름뿐이다. 문서 문자열(docstring)은 세지 않는다. — `tests/airgap/test_fork_rules.py`
6. **[필수]** OpenAI 호환 추론 surface(`/v1/chat/completions`, `/v1/models`)의 요청·응답 모양을 바꾸지 않는다. 클라이언트는 OpenAI SDK 를 그대로 쓴다. — 커밋 심사
