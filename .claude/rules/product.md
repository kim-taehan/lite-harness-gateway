# 제품 원칙

자동 검사가 없는 항목은 커밋 심사(`/convention-review`)와 사람이 지킨다. 잴 수 있는 부분은 `architecture.md` 5번이 막는다

1. 폐쇄망이 우선이다. 런타임 다운로드 0, telemetry·phone-home 0. 바깥 호출 대상은 내부 모델 서버(Ollama 등)와 내부 IdP(Keycloak)뿐이다. 바깥 요청이 기본으로 켜지는 upstream 기능은 꺼진 채로 둔다
2. LLM 클라이언트(OpenAI SDK, 코딩 도구)가 설정만 바꿔 그대로 쓸 수 있어야 한다. 추론 API 는 OpenAI 표준을 따른다
3. 관리 기능은 키·팀·예산·사용량을 운영자가 직접 다룰 수 있는 범위를 먼저 챙긴다. upstream 의 유료 기능을 흉내 내기보다 폐쇄망 운영에 필요한 것부터 한다
