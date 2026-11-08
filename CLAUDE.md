# lite-harness-gateway

폐쇄망용 LLM 게이트웨이. upstream litellm 의 fork 이고, 우리 작업은 `litellm_airgap` 브랜치에 쌓는다. `main` 은 upstream 을 그대로 따라간다

## 명령
- `sh scripts/airgap_check.sh`: 머지 조건. fork 가 바꾼 파일의 ruff, fork 규칙 검사(`tests/airgap/`), fork 단위 테스트를 돌린다. 종료 코드 0 이어야 한다
- `.venv/bin/python -m pytest tests/airgap -q`: fork 규칙 검사와 훅 테스트만
- `make lint`: upstream 린트 게이트. 무거워서 PR CI(`.github/workflows/airgap-ci.yml`)가 돌린다
- `docker-dev/`: Keycloak·Ollama 를 붙인 실물 환경. 필요할 때만

## 규칙
`.claude/rules/` 에 있다. workflow · architecture · code-quality · product · design-process
규칙은 거기에만 적고, 여기와 문서에는 링크만 둔다. 코딩 규약은 upstream 의 `AGENTS.md` 를 따르고, 브랜치·PR·커밋 같은 흐름은 `.claude/rules/workflow.md` 가 앞선다
훅(`.claude/settings.json`)이 main·litellm_airgap 직접 push, 검사 없는 머지, 심사 없는 커밋(`/convention-review`)을 막는다
작업자·리뷰어 에이전트는 `.claude/agents/` 에 있다

## 관련 저장소
lite-harness-desktop(데스크톱 앱), lite-harness-plugins(플러그인 원본·카탈로그)
