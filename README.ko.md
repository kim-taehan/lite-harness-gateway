# Lite Harness Gateway

[English](README.md) · **한국어**

**Lite Harness 폐쇄망 스택의 LLM 게이트웨이.**

Lite Harness Gateway 는 [LiteLLM](https://github.com/BerriAI/litellm) 포크로, 개발자와 모델(vLLM · Ollama · 사내 OpenAI 호환 서버 · 클라우드 API) 사이에 섭니다. 클라이언트는 OpenAI API 로 말하고, 사람은 회사 계정으로 로그인하며, 키 · 팀 · 팀원마다 예산과 일일 토큰 한도가 붙습니다. LiteLLM 이 하는 일은 그대로 다 됩니다. 이 포크는 폐쇄망에 필요했던 조각만 더합니다.

## 문제

회사 안에서 모델 하나를 같이 쓰려면 리버스 프록시로는 모자랍니다. 누군가 키를 나눠 주고, 그 키를 실제 계정에 묶고, 한 사람이나 한 팀이 하루치 GPU 를 다 쓰지 못하게 막고, 누가 얼마나 썼는지 봐야 합니다. LiteLLM 이 대부분을 해 주지만 몇 군데는 다른 환경을 가정합니다. 사용자 5명을 넘는 SSO 는 유료 등급이고, 일일 토큰 한도는 있지만 배치 작업만 셉니다. CLI 로그인(데스크톱 앱이 쓰는 흐름)은 외부 IdP 에 닿을 때만 됩니다.

## 아이디어

업스트림 LiteLLM 위에 머물고, 바꾸는 건 최소로.

1. **업스트림 프록시를 그대로 쓴다.** 포크는 `BerriAI/litellm` 을 따라가며 그 위에 커밋 몇 개만 얹습니다. 업스트림 수정과 provider 는 머지 한 번으로 계속 들어옵니다.
2. **회사 계정은 SSO 로.** 로그인은 범용 OIDC(우리 스택에서는 Keycloak)를 거칩니다. 무료 등급의 SSO 사용자 5명 상한은 `SSO_MAX_BILLABLE_USERS` 로 바꿀 수 있습니다(`0` 이면 없음).
3. **IdP 없이도 되는 CLI 로그인.** 데스크톱 앱이 CLI SSO 로그인을 시작했는데 SSO provider 가 설정돼 있지 않으면(또는 `CLI_SSO_PASSWORD_LOGIN` 을 켜면) 리다이렉트 대신 LiteLLM 이메일 · 비밀번호 폼을 보여 줍니다. 결과는 SSO 로그인과 같은 팀 범위 키입니다.
4. **실제로 걸리는 일일 토큰 한도.** 키 · 팀 · 팀원 예산의 `tpd_limit` 이 이제 chat completion 도 셉니다. 사용량은 UTC 하루 단위로 세고, 한도를 넘은 다음 요청은 429 를 받습니다.
5. **관리자용 읽기 전용 DB 조회(MCP).** `query_database` 가상 MCP 도구가 검증된 `SELECT` 하나를 읽기 전용 트랜잭션에서 statement timeout 과 행 수 상한을 걸고 실행합니다. proxy admin view 권한이 있는 키만 목록에서 보고 부를 수 있습니다.

전체 목록은 업스트림 위에 얹은 커밋 로그입니다.

```bash
git log --oneline main..litellm_airgap
```

## 브랜치

| 브랜치 | 담는 것 |
|---|---|
| `main` | 업스트림 `BerriAI/litellm` 미러. 포크 변경 없음. |
| `litellm_airgap` | 포크 본체: `main` + 위 커밋들. 여기서 브랜치를 따고 PR 도 여기로 엽니다. |

## 설치 · 실행

게이트웨이는 LiteLLM proxy 와 똑같이 돌고, 키 · 팀 · 사용량은 Postgres 에 둡니다. 이미지는 이 저장소에서 빌드합니다(폐쇄망에서는 업스트림 이미지를 받을 수 없고, 받더라도 포크 변경이 없습니다).

```bash
git clone -b litellm_airgap https://github.com/kim-taehan/lite-harness-gateway
cd lite-harness-gateway
docker build -t lite-harness-gateway .
```

OpenAI 호환 서버와 로컬 Ollama 를 가리키는 최소 `config.yaml`:

```yaml
model_list:
  - model_name: qwen3.5-122b
    litellm_params:
      model: openai/qwen3.5-122b
      api_base: http://<vllm-host>/v1
  - model_name: local-coder
    litellm_params:
      model: ollama_chat/<model>
      api_base: http://host.docker.internal:11434

litellm_settings:
  drop_params: true
```

```bash
docker run -p 4000:4000 \
  -e DATABASE_URL=postgresql://<user>:<password>@<db-host>:5432/litellm \
  -e LITELLM_MASTER_KEY=sk-<master-key> \
  -v $(pwd)/config.yaml:/app/config.yaml \
  lite-harness-gateway --config /app/config.yaml --port 4000
```

관리 화면은 `http://<host>:4000/ui` 입니다. 회사 계정 로그인은 범용 OIDC 변수(`GENERIC_CLIENT_ID`, `GENERIC_CLIENT_SECRET`, `GENERIC_AUTHORIZATION_ENDPOINT`, `GENERIC_TOKEN_ENDPOINT`, `GENERIC_USERINFO_ENDPOINT`, `PROXY_BASE_URL`)를 Keycloak realm 에 맞추고, 사용자 상한을 풀려면 `SSO_MAX_BILLABLE_USERS=0` 을 줍니다.

그 밖의 모든 것(provider · 라우팅 · 예산 · 로깅 · 설정 항목 전부)은 업스트림 동작입니다. [LiteLLM 문서](https://docs.litellm.ai/docs/simple_proxy)와 [업스트림 README](https://github.com/BerriAI/litellm#readme)를 보세요.

## 사용

**Lite Harness 데스크톱에서는** 설정 → 모델 → `+ provider 추가` 에서 `http://<host>:4000/v1` 과 관리 화면에서 만든 API 키를 넣습니다. 아니면 **SSO 로그인** 을 켜고 회사 계정으로 로그인합니다. 그러면 앱이 팀 키를 받고, 그 키가 쓸 수 있는 모델 목록을 보여 줍니다.

**아무 OpenAI 클라이언트에서나:**

```bash
curl http://<host>:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-<your-key>" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3.5-122b", "messages": [{"role": "user", "content": "hello"}]}'
```

**일일 토큰 한도** 는 다른 LiteLLM 한도처럼 키 · 팀 · 팀원 예산에 `tpd_limit` 으로 겁니다.

```bash
curl http://<host>:4000/key/generate \
  -H "Authorization: Bearer sk-<master-key>" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<team-id>", "tpd_limit": 2000000}'
```

## 관련 저장소

Lite Harness 는 함께 나가는 저장소 셋으로 이뤄집니다.

```
 lite-harness-plugins ──(설치 파일 · catalog.json + 확장 zip)──▶ lite-harness-desktop
                                                                      │  OpenAI 호환 API
                                                                      │  (API 키 또는 회사 SSO)
                                                                      ▼
                                                              lite-harness-gateway (이 저장소) ──▶ LLM (vLLM · Ollama · 클라우드 …)
```

| 저장소 | 역할 | 이 저장소와의 관계 |
|---|---|---|
| [lite-harness-desktop](https://github.com/kim-taehan/lite-harness-desktop) | 데스크톱 앱(Electron)과 Android 앱(`mobile/`) | 주 클라이언트입니다. 설정 → 모델 에서 API 키로 붙거나, **SSO 로그인**(CLI SSO 흐름: `/sso/cli/start` → `/sso/key/generate?source=litellm-cli` → `/sso/cli/poll`)으로 팀 키와 그 계정이 쓸 수 있는 모델 목록을 받아 옵니다. |
| [lite-harness-plugins](https://github.com/kim-taehan/lite-harness-plugins) | 배포 저장소: 앱 설치 파일(`app-v<버전>` 릴리스)과 확장(`catalog.json` + `dist/*.zip`) | 직접 관계는 없습니다. 사용자는 여기서 앱을 받은 뒤 이 게이트웨이에 연결합니다. |
| **lite-harness-gateway** (이 저장소) | LLM 게이트웨이, 폐쇄망 스택용 [LiteLLM](https://github.com/BerriAI/litellm) 포크(Keycloak SSO, 키 · 팀 예산, 일일 토큰 한도) | — |

## 개발

개발은 업스트림 LiteLLM 을 따릅니다. 환경 구성 · 테스트 · lint 게이트는 [CONTRIBUTING.md](CONTRIBUTING.md) 와 [AGENTS.md](AGENTS.md) 에 있습니다. `litellm_airgap` 에서 `litellm_` 접두어로 브랜치를 따고 PR 은 `litellm_airgap` 으로 엽니다.

업스트림 반영:

```bash
git fetch upstream            # upstream = https://github.com/BerriAI/litellm
git checkout main && git merge --ff-only upstream/main && git push origin main
git checkout litellm_airgap && git merge main
```

`README.md` 와 `README.ko.md` 는 포크 것입니다. 업스트림 머지에서 충돌하면 우리 쪽을 남깁니다.

[`GATEWAY_DESIGN.md`](GATEWAY_DESIGN.md) 는 Python proxy 를 독립 Kotlin 게이트웨이로 갈아 끼우려던 이전 설계입니다. 그 재작성은 Python proxy 에 머물기로 하면서 접었으므로(`edf9fbacf3`) 현재 구조가 아니라 배경 자료로 읽어 주세요.

## 범위 · 철학

- **업스트림 우선.** 폐쇄망 스택에 필요할 때만 포크에 넣고, 업스트림 머지가 싸게 유지되도록 작게 둡니다.
- **LiteLLM 과 같은 API.** 클라이언트와 관리자는 표준 LiteLLM 엔드포인트를 씁니다. 포크는 설정을 더할 뿐 새로 배울 표면을 만들지 않습니다.
- **새 게이트웨이가 아님.** 이 README 에 없는 것은 업스트림 문서가 기준입니다.
