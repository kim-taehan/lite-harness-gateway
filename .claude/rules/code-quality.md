# 코드 품질

단순함이 먼저다. 코딩 규약(Final, frozen 모델, Any 금지, 함수형 우선 등)은 루트 `AGENTS.md` 를 그대로 따른다. 여기는 fork 에서 더 지킬 것만 적는다
**[필수]** 는 지켜야 하고, **[검토]** 는 어기면 PR 에 이유를 적는다(심사는 확인 질문으로만 남긴다)
[필수] 줄 끝의 `— tests/…` 는 그 규칙을 자동으로 막는 검사, `— 커밋 심사` 는 자동 검사가 없어 `/convention-review` 와 사람이 지키는 것이다

## 의존성
1. **[필수]** 새 패키지를 넣지 않는다. Python 은 `pyproject.toml`·`uv.lock` 를 fork 에서 바꾸지 않는 것으로 잰다. UI(`ui/`)의 `package.json` 과 잠금 파일, requirements 파일은 커밋 심사가 본다. 폐쇄망 이미지는 upstream 과 같은 잠금 파일로 만든다. 꼭 필요하면 리더와 정한 뒤 이 규칙과 검사를 함께 바꾼다. — `tests/airgap/test_fork_rules.py` + 커밋 심사(UI·requirements)
2. **[필수]** `AGENTS.md` 의 코딩 규약을 어기는 개수가 PR 대상 브랜치보다 늘지 않는다(ruff strict·타입 규칙·basedpyright·테스트 품질 게이트). — `.github/workflows/airgap-ci.yml`

## 비밀 값
3. **[필수]** 키·토큰·비밀번호·Authorization 값을 로그(`*logger.*`, `logging.*`, `print`)에 넘기지 않는다. 마스킹하거나 해시·이름만 남긴다. — `tests/airgap/test_fork_rules.py`
4. **[필수]** 키·토큰·비밀번호를 API 응답 본문, 에러 메시지, 예외 문자열에 담지 않는다. — 커밋 심사

## 테스트
5. **[필수]** fork 가 바꾼 `litellm/` 소스 파일마다 `tests/unit/` 의 같은 경로에 짝 테스트 파일이 있다(`litellm/a/b.py` 는 `tests/unit/a/test_*b*.py`). — `tests/airgap/test_fork_rules.py`
6. **[필수]** 테스트는 내부 구조가 아니라 동작(결과)을 본다. 버그를 고치면 그 버그가 다시 생길 때 실패하는 테스트를 붙인다. — 커밋 심사
7. **[필수]** 단위 테스트는 빨라야 한다. fork 가 만든 테스트 파일 하나의 테스트 본문 합은 3초, 테스트 하나(준비·정리 포함)는 2초 안. 파일 합에서 준비 시간을 빼는 까닭은 upstream 의 autouse fixture 가 테스트마다 30ms 쯤 들어서다. 실제 시간·네트워크·DB 를 기다리지 않고 가짜 시계·가짜 의존으로 쓴다. 실물이 꼭 필요하면 `tests/e2e/` 로 둔다. — `tests/airgap/slow_gate.py`
8. **[필수]** Claude Code 훅의 판정은 순수 함수로 두고 테스트를 붙인다. 훅은 오류가 나면 명령을 막는다(그냥 통과시키지 않는다). — `tests/airgap/test_hooklib.py`

## 읽기 쉬운 코드
9. **[필수]** 내 변경으로 안 쓰게 된 import·변수·함수는 지운다. 원래 있던 죽은 코드는 지적만 하고 요청 없이는 지우지 않는다. — 커밋 심사
10. **[검토]** 함수는 한 가지 일만 한다. 50줄을 넘으면 나눌지 따진다. 깊은 중첩 대신 일찍 돌려준다
11. **[검토]** 이름은 하는 일을 말한다. `util`·`helper`·`manager` 같은 뭉뚱그린 이름을 피한다
12. **[검토]** 같은 코드가 세 번 나오면 함수로 뺀다. 두 번까지는 그대로 둬도 된다
