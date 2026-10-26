# LLM Gateway 설계서 (클린슬레이트)

> 대상: `litellm/proxy` (Python) 를 완전 대체하는 자립형 LLM 게이트웨이
> 작성일: 2026-10-26
> 상태: M0 착수 대기 (오픈 결정 13.1~13.3 확인 필요)
> 참고 문서: `ANALYSIS.md` (코드베이스 분석), `SSO_ANALYSIS.md` (SSO 4플로우), `PREMIUM_WALL_REVIEW.md`, `KO_I18N_REVIEW.md`
> 이문서는 소각된 `KOTLIN_REDESIGN.md` (기존 `kotlin-backend/` 재활용 방향) 를 대체한다. `kotlin-backend/` 는 기반이 아니며, 일부 유닛만 재평가 대상 (10장)

---

## 1. 정의

### 1.1 대체 대상

Python `litellm.proxy` 가 폐쇄망 스택에서 수행하는 기능 전체. 구체적으로 Inference (OpenAI 표준 chat completions + model listing), 인증 (API key + SSO), 관리 (key/team/budget), 사용량/비용 회계이다.

### 1.2 미대체 대상

| 구성품 | 역할 | 비고 |
|---|---|---|
| Ollama (`devstral:24b`) | 모델 런타임, host :11434 | gateway가 호출하는 provider일 뿐 |
| ko-dashboard (`ui/ko-dashboard/`) | React SPA, nginx :4101 | API spec이 달라지므로 4 뷰 + `api.ts` 수정 필요 (M2, 1~2인일) |
| Keycloak 26.1 | OIDC IdP, :4115, realm `litellm` | 그대로 재사용. client 구성만 추가 |

### 1.3 액터

| 액터 | 설명 | 접근 surface |
|---|---|---|
| LLM 클라이언트 | OpenAI SDK / curl / 에이전틱 코딩 도구 | `POST /v1/chat/completions` (stream+non), `GET /v1/models`, API key 인증 |
| admin / user | ko-dashboard 사용자 | `/api/v1/*` (SSO JWT 인증) |
| IdP (Keycloak) | OIDC authorization code + PKCE | gateway만 호출 (server-to-server token exchange) |
| Provider (Ollama) | OpenAI호환 추론 서버 | gateway만 호출 |

---

## 2. 설계 원칙

| # | 원칙 | 내용 |
|---|---|---|
| (a) | Inference surface은 OpenAI 표준 | `POST /v1/chat/completions`, `GET /v1/models` 만 OpenAI 호환. 클라이언트가 OpenAI SDK 를 그대로 쓴다 |
| (b) | Admin surface은 자체 spec | `/api/v1/*` 로 자체 정의. LiteLLM admin API shape 을 따라갈 의무 없음. shape 은 golden test 로 고정 (7장) |
| (c) | 독립 스키마 | 7 테이블 (4장). LiteLLM 의 Prisma 스키마/테이블명 (`litellm_verification_token_v1` 등) 의존 없음. DDL 은 Flyway 로 자체 생성 |
| (d) | Virtual threads | JDK 21 virtual threads 로 request 처리. 2~3초 LLM 대기의 부하는 근소 (3.1) |
| (e) | Provider는 SPI | `LlmProvider` 인터페이스로 추상화. 1차 구현은 OpenAI-compatible (Ollama) 1종 |
| (f) | Air-gapped zero external call | phone-home, telemetry, 외부 폰트/CDN 일절 없음. 외부 호출 대상은 Ollama + Keycloak (내부) 만 |
| (g) | 프로젝트명 | TBD, working name `llm-gateway` (오픈 결정 13.1) |

---

## 3. 아키텍처

### 3.1 구성 다이어그램

```
 LLM 클라이언트 (OpenAI SDK / curl / 코딩 도구)
   │  Authorization: Bearer sk-...
   │  POST /v1/chat/completions (stream / non-stream)
   │  GET  /v1/models
   ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ llm-gateway :4000 (Kotlin 21, virtual threads)               │
 │   /v1/*  inference surface     /api/v1/*  admin surface      │
 └──────┬──────────────────┬────────────────────┬───────────────┘
        │ inference        │ persistence        │ SSO token exchange
        ▼                  ▼                    ▼
  Ollama :11434       Postgres :5434        Keycloak :4115
  (devstral:24b)      (db, Flyway V1)       (realm litellm)

 ┌──────────────────────────────────────────────────────────────┐
 │ ko-dashboard (nginx :4101, static SPA)                       │
 │   /api/*  ─────────────────────────▶ llm-gateway :4000       │
 │   browser ─302 login─▶ Keycloak :4115                        │
 │   callback: http://localhost:4101/api/v1/auth/callback       │
 │            (nginx → llm-gateway, JWT 쿠키 세팅)               │
 └──────────────────────────────────────────────────────────────┘
```
- LLM 클라이언트는 gateway :4000 에 `Authorization: Bearer sk-...` 로 직결
- ko-dashboard 는 nginx :4101. SPA.static 제공은 nginx 가, 모든 API(`api/*`)는 gateway 로 proxy
- SSO 로긴 콜백 URI 는 `http://localhost:4101/api/v1/auth/callback` (nginx 경유, gateway 처리)
- Ollama 는 host 쪽 (`host.docker.internal:11434`). gateway 의 base_url 은 컨테이너 관점에서 `http://host.docker.internal:11434`

### 3.2 Kotlin 패키지 구조

```
llm-gateway/
├── build.gradle.kts          # Spring Boot 3.x, JDK 21, virtual threads
├── settings.gradle.kts
└── src/main/
    ├── resources/db/migration/
    │   └── V1__init.sql      # Flyway DDL (4장 전체) + dev 시드
    └── kotlin/ai/airgap/gateway/
        ├── GatewayApplication.kt
        ├── api/              # HTTP 레이어: InferenceController(/v1/*), SsoController, HealthController
        ├── inference/        # ChatPipeline, LlmProvider SPI, OpenAiCompatibleProvider, SseStream, UsageCapture
        ├── auth/             # KeyVerifier, KeyCache(30s), SsoService, JwtIssuer, RefreshTokenService
        ├── admin/            # /api/v1/* 컨트롤러 + 서비스 (Key/Team/Model/SpendQuery)
        ├── billing/          # 정적 rate 테이블, cost 계산, spend 집계 쿼리
        └── core/             # config, DataSource, error envelope, structured logging, metrics, Flyway
```

- 프레임워크는 Spring Boot 3 (검증된 스택, `kotlin-backend/` 와 동일 계열)
- HTTP 서버는 virtual threads 로 구동 (`spring.threads.virtual.enabled=true`). Tomcat 200 스레드 수는 더 이상 병렬 상한이 아님

### 3.1 부하 논증: LLM 대기 2~3초는 proxy 부하인가

**아님.** 근거:

1. request 당 virtual thread 1개. LLM 응답 대기 중 해당 thread 는 **parked** 상태이며 platform 스레드와 메모리를 차지하지 않는데 비용은 KB 수준
2. Tomcat 컨테이너 스레드 수 (200) 는 virtual threads 모드에서 병렬 상한에서 해제됨
3. 실제 병렬 상한은 **Ollama 의 GPU 병행성** (1 GPU 로 몇 개의 `devstral:24b` 생성을 동시에 돌리나). 이를 per-deployment semaphore (`model_deployment.concurrency`, 5.2 Step 4) 로 명시적으로 throttle
4. 따라서 300개 동시 × 2.5초 대기 = parked virtual thread 300개 ≈ 수 MB. 게이트웨이 측 병목 없음
5. inference request 는 완료 시점에 `request_log` INSERT 1행 + `api_key`/`team` spend UPDATE 1회로 DB 접근이 끝나므로 Hikari pool (10~15) 도 병목 아님

이 논거는 9.5 장 load 테스트 (300 concurrent, 고갈 없음, p95 안정) 로 실험적으로 검증한다.

---

## 4. 스키마 (Flyway V1)

7 테이블. LiteLLM 테이블명과 무관한 독립 스키마.

### 4.1 `user`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| email | text unique NOT NULL | SSO claim 에서 upsert 키 |
| name | text | |
| role | text check in ('admin','user') | 기본 'user'. bootstrap admin 은 env/시드로 지정 |
| sso_subject | text unique nullable | Keycloak `sub` |
| created_at | timestamptz | |

### 4.2 `api_key`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| name | text NOT NULL | 표시용 |
| key_hash | text unique NOT NULL | SHA-256(hex). 원문은 생성 시 1회만 노출, 재조회 불가 |
| key_prefix | text not null | 표시용 접두 (예: `sk-gw-ab12`) |
| is_master | bool default false | bootstrap master key (6.1) |
| user_id | uuid fk nullable | 소유자 |
| team_id | uuid fk nullable | 소속 팀 |
| models | text[] default {'*'} | 허용 모델 allow list |
| max_budget | numeric(12,6) nullable | NULL = 무제한 (USD, 내부 회계) |
| spend | numeric(12,6) default 0 | 원자적 증가 accumulator |
| expires_at | timestamptz nullable | NULL = 만료 없음 |
| deleted_at | timestamptz nullable | soft delete = 즉시 폐기 (캐시 만료 대기) |
| last_used_at | timestamptz | |
| created_at | timestamptz | |

### 4.3 `team`

`id uuid PK`, `name text unique NOT NULL`, `max_budget numeric(12,6) nullable`, `spend numeric default 0`, `created_at`. 팀-사용자는 `team_member` 로 연결.

### 4.4 `team_member`

`team_id uuid fk`, `user_id uuid fk`, `role text in ('admin','member')`, PK(team_id, user_id).

### 4.5 `model_deployment`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| model_name | text NOT NULL | 대외 모델명 (client 가 요청하는 이름) |
| provider | text NOT NULL | 1차: `openai_compatible` |
| base_url | text NOT NULL | 예: `http://host.docker.internal:11434` |
| model_id | text NOT NULL | provider 쪽 실제 모델 (예: `devstral:24b`) |
| api_key | text nullable | provider 인증 (내부, 암호화 저장 정책은 env secret) |
| active | bool default true | |
| concurrency | int NOT NULL | semaphore 병행도 (5.2 Step 4). Ollama parallelism 반영, default 4 (오픈 결정 13.3) |
| created_at | timestamptz | |

인덱스 (model_name, active). `model_name` 1 개 → deployment N 개 (1:N). 1차는 active 중 첫 것을 선택하며, LB/fallback 전략은 SPI hook 만 남겨 놓음 (12장 non-goal).

### 4.6 `request_log`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| request_id | uuid PK | |
| created_at | timestamptz NOT NULL | desc index, spend 로그 기본 정렬 |
| key_id | uuid fk | NULL 가능 (master key 는 user_id 로만) |
| user_id | uuid fk nullable | |
| team_id | uuid fk nullable | |
| model | text NOT NULL | |
| prompt_tokens / completion_tokens / total_tokens | int | |
| usage_source | text in ('provider','estimate') | provider 가 usage 를 주면 'provider', 없으면 bytes/4 추정 'estimate' (5.3) |
| cost | numeric(12,6) | rate 테이블 기준 USD (6.3) |
| latency_ms | int | 첫 바이트~종료. stream 의 경우 종료 시점 |
| status | text in ('success','error') | |
| error | text nullable | error.class (예: `timeout`, `provider_5xx`) |

인덱스: (created_at desc), (key_id), (team_id), (model, created_at). 파티셔닝은 1차 미적용 (폐쇄역 규모).

### 4.7 `sso_session`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid fk | |
| refresh_token_hash | text unique NOT NULL | opaque refresh token 의 SHA-256. 원문은 cookie 로만 존재 |
| expires_at | timestamptz NOT NULL | 발급 시점 + 30d |
| last_rotated_at | timestamptz | rotation 이력 (재사용 감지) |
| revoked_at | timestamptz nullable | logout/rotation 시 |
| created_at | timestamptz | |

### 4.8 DDL (V1__init.sql 요지)

```sql
create table user (...);              -- 4.1
create table team (...);              -- 4.3
create table team_member (...);       -- 4.4
create table model_deployment (...);  -- 4.5
create table api_key (...);           -- 4.2
create table request_log (...);       -- 4.6
create table sso_session (...);       -- 4.7

-- dev 시드 (폐쇄역 고정 구성)
insert into model_deployment (model_name, provider, base_url, model_id, concurrency)
  values ('devstral', 'openai_compatible', 'http://host.docker.internal:11434', 'devstral:24b', 4);
```

시드는 M4 시점에 Flyway 시드 migration 으로 분리한다 (운영 DB 시드는 admin API `POST /api/v1/models` 책임).

---

## 5. Inference

### 5.1 Provider SPI

```kotlin
interface LlmProvider {
    val providerId: String
    fun chat(req: ChatRequest): Flow<StreamEvent>   // non-stream 은 단 2개 event (content, [done])
    fun models(): List<ModelInfo>                    // GET /v1/models
}

sealed interface StreamEvent {
    data class Chunk(val sse: String) : StreamEvent            // provider 원본 SSE frame
    data class Usage(val prompt: Int, val completion: Int) : StreamEvent
    data class Done(val status: Result) : StreamEvent
}
```

- 1차 구현 `OpenAiCompatibleProvider`: OkHttp + SSE reader. Ollama `/v1/chat/completions` 은 OpenAI형 SSE 를 네이티브 지원하므로 body 는 거의 byte pass-through
- 1 request 1 deployment. 라우팅 (1:N 선택) 은 `inference/DeploymentSelector` 인터페이스

### 5.2 Request path (7단계)

| step | 처리 | 실패 시 |
|---|---|---|
| 1. key verify | `Authorization: Bearer` 또는 `x-api-key` → SHA-256 → 30s 캐시 → `api_key` 조회. `deleted_at`/`expires_at`/allow list 체크 | 401 / 403 |
| 2. budget check | `key.spend < key.max_budget` 및 소속 team budget. (TPM 같은 토큰 기반 동적 limit 는 non-goal) | 429 `budget_exceeded` |
| 3. deployment select | `model_name` → active deployment 조회. 없으면 404 `model_not_found` | 404 |
| 4. semaphore | per-deployment `Semaphore(concurrency)`. acquire 대기 (timeout) | 429 `rate_limited` |
| 5. forward | provider 로 stream forwarding. stream 요청에는 `stream_options.include_usage=true` 주입. usage 는 마지막 chunk 가 전달, 없으면 요청+응답 bytes/4 추정 + `usage_source=estimate` | 502/504 envelope |
| 6. request_log | `request_log` INSERT 1행 + `api_key.spend`/`team.spend` 원자적 UPDATE (request 종료 시점, 1 트랜잭션) | 로그 실패는 request 를 실패로 만들지 않음 (warn log) |
| 7. respond | 클라이언트 로 스트림 반환 (non-stream 은 JSON 전체) | - |

- timeout: connect 5s / read 300s (24b 로컬 생성은 느림을 전제)
- retry: **0**. inference 는 재시도로 생성 2배가 되므로, 재시도는 클라이언트 책임
- stream 중간 단절: 이미 stream-start 된 request 가 provider 죽으면 `data: [DONE]` 없이 종료 + `request_log` status=error. 부분 usage 는 추정치

### 5.3 Error envelope (OpenAI 표준)

```json
{ "error": { "message": "...", "type": "authentication_error | permission_error | invalid_request_error | rate_limit_error | server_error", "code": "401" } }
```

| 상황 | HTTP | type |
|---|---|---|
| key 없음/형식 오류 | 401 | authentication_error |
| key 폐기/만료 | 401 | authentication_error |
| 모델 not allowed | 403 | permission_error |
| budget 초과 / semaphore 초과 | 429 | rate_limit_error |
| 모델 미등록 | 404 | invalid_request_error |
| provider connection/timeout | 503 | server_error |
| provider 5xx | 502 | server_error |

---

## 6. Auth

### 6.1 API key

- 저장: SHA-256 hex (`key_hash`, unique index). 원문은 `POST /api/v1/keys` 응답에서 **1회만** 반환
- 검증 캐시: `ConcurrentHashMap<key_hash, CachedKey>` TTL 30s. soft delete 만료 전까지 폐기 key 가 살아있는 윈도우 (허용, 폐기는 즉시 API 차단)
- allow list: `models[]` 가 `{'*'}` 가 아니면 요청 모델 포함 체크 (403)
- master key: `is_master=true`. 앱 기동 시 env (`GATEWAY_MASTER_KEY`) 에 없으면 생성 후 log 1회 노출. allow list / budget 무제한, `/api/v1` 의 `Bearer` 인증도 가능 (에디프 호환)
- spend 증가: request 완료 트랜잭션에서 `set spend = spend + $cost`. budget check 는 read 시점 값 기준 (race 허용 범위: 폐쇄역, 오차는 request 단위로 수 cent 이하)

### 6.2 SSO (Keycloak OIDC)

플로우 (authorization code + PKCE, public client):

1. `GET /api/v1/auth/login` → gateway 가 `code_challenge` 생성 → Keycloak `auth` URL 로 302
2. `GET /api/v1/auth/callback?code=...` → server-side token endpoint 에서 code exchange
3. `id_token`/`user_info` 의 `email` claim → `user` upsert (role='user', sso_subject=sub)
4. 발급: access JWT (HS256, **15분**, sub=user.id, email, role) + opaque refresh token (256bit random)
   - refresh token 은 `sso_session.refresh_token_hash` 로만 저장, 원문은 HttpOnly cookie 로만 존재
   - redirect 로 SPA 에 진입 (cookie + access token 전달)
5. `POST /api/v1/auth/refresh` (cookie) → rotation (새 토큰 발급, 구 토큰 revoked). 유효 기한 30d
6. `POST /api/v1/auth/logout` → 해당 `sso_session` revoked + cookie clear. Keycloak 의 RP-initiated logout 은 1차 미적용 (air-gap 내 session 만 무효화하면 충분)
7. 재사용 감지: revoked 상태 refresh token 으로 refresh 시 그 user 의 모든 session 무효화 + warn log

Keycloak 구성: realm `litellm` 과 기존 client 는 유지하되, **새 public client `llm-gateway`** 추가 (redirect `http://localhost:4101/api/v1/auth/callback`, PKCE). 기존 `litellm-proxy` client 는 Python 삭제 후 dead asset 이므로 M4 시 정리.

### 6.3 비용 계산

정적 rate 테이블 (코드 내 resource, `rates.yaml`):  모델 family → (input USD/1M, output USD/1M). 폐쇄역 내부 회계이므로 **default 0** (Ollama 로컬 모델은 비용이 0. external 모델 시에만 값 입력). `request_log.cost` 는 이 테이블로 계산하며, rate 없으면 `cost=0`.

---

## 7. Admin API (자체 spec, `/api/v1`)

인증: SSO access JWT (Bearer) 또는 master key. shape 은 golden test 로 고정 (9.3).

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/me` | 현재 사용자 (email, role, teams) |
| GET | `/api/v1/keys` | 열람 (prefix, owner, team, models, budget, spend, expires, last_used) |
| POST | `/api/v1/keys` | 생성. 응답에 원문 key 1회 포함, 그 외에는 prefix/hash 로만 |
| GET | `/api/v1/keys/{id}` | 상세 |
| PATCH | `/api/v1/keys/{id}` | name / models / max_budget / expires_at / team_id 수정 |
| DELETE | `/api/v1/keys/{id}` | soft delete (즉시 폐기) |
| GET | `/api/v1/teams` | team 목록 (spend, budget, members) |
| POST | `/api/v1/teams` | 생성 |
| GET | `/api/v1/teams/{id}` | 상세 + 멤버 |
| PATCH | `/api/v1/teams/{id}` | name / max_budget |
| DELETE | `/api/v1/teams/{id}` | 멤버가 key 를 들고 있으면 409 |
| GET | `/api/v1/models` | deployment 목록 (model_name, provider, base_url, concurrency, active) |
| POST | `/api/v1/models` | deployment 추가 (운영 시드) |
| PATCH | `/api/v1/models/{id}` | active / concurrency / base_url 수정 |
| GET | `/api/v1/spend/logs?from&to&model&key&team&page&size` | `request_log` 페이지닝 조회 |
| GET | `/api/v1/spend/summary?by=user\|team\|model&from&to` | 집계 (total_cost, total_requests, token 수) |
| GET | `/healthz` | liveness (DB ping 포함, compose healthcheck) |
| GET | `/metrics` | Prometheus text (8.2) |

권한 모델: `role=admin` 은 전체. `role=user` 는 자신의 key/team 만 (1차 단순화, 세부 ACL 은 non-goal).

### 7.1 ko-dashboard 마이그레이션 (M2, 1~2인일)

`api.ts` + 4 뷰 (개요/로그/비용/키) 를 위 spec 에 맞게 수정. 현재 호출 엔드포인트 매핑:

| 현재 (LiteLLM) | 신규 (llm-gateway) |
|---|---|
| `GET /user/info` | `GET /api/v1/me` |
| `GET /key/list` | `GET /api/v1/keys` |
| `POST /key/generate` | `POST /api/v1/keys` |
| `GET /key/info` | `GET /api/v1/keys/{id}` |
| `GET /spend/users` | `GET /api/v1/spend/summary?by=user` |
| `GET /global/spend` | `GET /api/v1/spend/summary?by=model` (total 필드) |
| `GET /global/spend/teams` | `GET /api/v1/spend/summary?by=team` |
| `GET /global/spend/models` | `GET /api/v1/spend/summary?by=model` |
| `GET /v1/models` | 동일 (OpenAI 표준) |
| `GET /spend/logs/v2` | `GET /api/v1/spend/logs` |

로그인 방식: 현재 API key 입력 (`ApiKeyPrompt`) → SSO 버튼 (M3) + master key 입력 (호환 둘 다 유지).

---

## 8. 관측/운영

### 8.1 로깅

- JSON structured log (request_id, key_id, model, status, latency)
- `request_id` 는 request 진입 시 uuid 생성, MDC 에 바인딩. 구조화 로그 전 라인에 포함
- `request_log` 표는 비용/집계용, structured log 는 debug/추적용

### 8.2 Prometheus metrics

| metric | 타입 | 라벨 |
|---|---|---|
| `gateway_http_requests_total` | counter | path_group, status |
| `gateway_inference_in_flight` | gauge | - |
| `gateway_inference_duration_seconds` | histogram (p95) | model |
| `gateway_ttft_seconds` | histogram | model (첫 SSE chunk 까지) |
| `gateway_semaphore_wait_seconds` | histogram | deployment_id |
| `gateway_spend_total` | counter (USD) | model |

### 8.3 compose (M4 최종)

```yaml
services:
  db:          postgres:16-alpine, :5434
  gateway:     llm-gateway (temurin:21-jre-alpine base), :4000
  keycloak:    keycloak:26.1, :4115 (기존 realm 볼륨 유지)
  ko-dashboard: nginx:1.27-alpine, :4101, /api/* -> gateway:4000
```

- 삭제: `litellm` 서비스, Python 빌드 컨텍스트, `docker-dev/config.yaml` (model_list 는 `model_deployment` 표로 이동)
- gateway env: `GATEWAY_DB_URL`, `GATEWAY_MASTER_KEY`, `GATEWAY_JWT_SECRET`, `GATEWAY_KEYCLOAK_URL`, `GATEWAY_KEYCLOAK_CLIENT_ID`
- 이미지는 다단계 빌드 (compile: temurin:21-jdk → runtime: temurin:21-jre-alpine)

---

## 9. 테스트 전략

"feat 추가 전엔 실패, mutate 시 깨진다"를 기준으로만 쓴다 (AGENTS.md 테스트 정책 준수).

### 9.1 Unit

| 대상 | 검증 |
|---|---|
| UsageCapture | provider usage / `stream_options` 주입 유무 / bytes/4 추정 + `usage_source=estimate` |
| BudgetCheck | `spend < max_budget` 경계, team budget, NULL=무제한 |
| KeyVerifier | hash 일치/불일치, allow list, 만료, soft delete, 캐시 TTL |
| SseStream | `[DONE]`, 중간 단절, usage 없는 마지막 chunk |
| cost | rate 테이블 lookup, rate 없음=0, 1M 단위 반올림 |

### 9.2 Contract (inference)

- embedded fake OpenAI 서버 (WireMock 또는 자립 Netty stub) 로 `/v1/chat/completions` SSE 시나리오 (완전 stream, 중간 5xx, usage 부재, timeout) 에 대한 golden JSON 대조
- error envelope shape (5.3) 고정

### 9.3 Admin golden

`/api/v1` 전체 response shape (200/401/403/404/409 케이스) golden JSON. ko-dashboard 의 `api.ts` 계약이 이 golden 에 근거한다.

### 9.4 E2E (실 Ollama + compose)

1. `docker compose up` (db + gateway + keycloak + ko-dashboard)
2. curl 로 1턴 chat completions (stream + non-stream)
3. `GET /api/v1/spend/logs` 로 1행 확인 (token 수 > 0, cost, model=devstral)
4. 키 생성 (admin API) → ko-dashboard (headless 브라우저) 에서 신규 key 생성 후 목록에 prefix 표시 확인
5. SSO: Keycloak 로긴 후 `/api/v1/me` 200

### 9.5 Load

- 300 concurrent × ~2.5s streaming requests (Ollama 실제 처리)
- 기준: request 고갈 (5xx/timeout) 없음, p95 latency 안정 (provider 한계 내에서), `request_log` 300행 모두 기록, semaphore wait 분포 확인으로 3.1 부하 논증 실증

### 9.6 Failure

- Ollama down: `POST /v1/chat/completions` → 503 envelope, `request_log` status=error 기록, gateway 는 다른 request 정상 처리 (survival 확인)
- DB down: `/healthz` 실패, inference 503, 프로세스 crash 아님
- expired/삭제된 key: 401 (캐시 TTL 30s 이내 폐기)

---

## 10. 기존 `kotlin-backend/` 처리

**기반 X.** `litellm_verification_token_v1` 등 LiteLLM 테이블명, Starlette 호환 error layer 등 LiteLLM 추종 구조는 새 스키마/API 전제와 충돌. M4 cutover (python 제거 + 로드/E2E 통과) 완료 후 디렉터리 삭제 (git 역사로 아카이브).

재평가 유닛 후보 (문제를 푼 것이 아니라 검증된 코드만):

| 유닛 | 위치 | 재평가 관점 |
|---|---|---|
| JWT/HMAC 유틸 | `auth/UiSessionJwt.kt` | HS256 발행/검증 로직만. LiteLLM claim 구조 배제 후 재사용 가능 |
| SHA-256 hashing | `auth/Hashing.kt` | 단순. 재사용 or 재작성 모두 비용 낮음 |
| error envelope 패턴 | `web/ProxyError.kt` / `ProxyErrorController.kt` | 스타일만 참고, shape 은 OpenAI 표준 (5.3) 으로 변경 |
| golden test 방법론 | `DataLayerRoundTripTest`, `KeyContractGoldenTest` | 9.2/9.3 의 golden test 구조를 그대로 차용 |

---

## 11. 마일스톤

| MS | 범위 | 산출 기준 | 인력 |
|---|---|---|---|
| M0 | Scaffold | Gradle/temurin21/virtual thread, compose (db+gateway), Flyway V1 7 테이블, `/healthz`, 로컬 기동 | 1~2 |
| M1 | Inference core | `/v1/chat/completions` (stream+non) + `/v1/models`, key verify + budget, usage capture, `request_log`, error envelope, unit+contract test | 4~5 |
| M2 | Admin + ko-dashboard | `/api/v1/*` 전체 + golden test, ko-dashboard `api.ts` + 4 뷰 수정 (7.1), spend 로그/요약 화면 | 4~5 |
| M3 | SSO | OIDC code+PKCE, session/rotation/logout, Keycloak client 추가, ko-dashboard 로긴 화면 | 2~3 |
| M4 | Cutover | parallel (python+gateway) → 트래픽 전환 → python 제거 → load (9.5)/failure (9.6) 검증 → `kotlin-backend/` 아카이브 | 2 |
| | **합계** | | **13~17** |

---

## 12. Non-goals (1차)

- OpenAI-compatible 외 provider (Bedrock/Gemini raw API 등). SPI 로 추가 가능한 구조만 유지
- `/v1/messages` (Anthropic surface) 는 13.2 확인 전까지 미포함
- guardrails / content moderation
- 토큰 기반 동적 rate-limit (TPM/TPS). key 레벨 기본 RPM limit 만 (2단계 1)
- batch / embedding / image / fine-tuning endpoint
- multi-deployment 로드밸런싱/폴백 (1:N 구조만, 전략은 SPI hook)
- Redis 등 추가 의존 (in-memory 캐시 + Postgres 만)
- 다중 region / HA / 수평 확장 (폐쇄역 단일 인스턴스)

---

## 13. 오픈 결정 (M0 착수 전 확인 필요)

### 13.1 서비스/디렉터리 최종명

working name `llm-gateway`, 패키지 `ai.airgap.gateway`. 최종 서비스명 (image명, compose service, 디렉터리) 확정.

### 13.2 LLM 클라이언트 인벤토리

게이트웨이에 붙일 클라이언트를 확정하라:

- Claude Code / Codex 등 **Anthropic API 기반** 툴을 붙일 계획이 있는가? 있으면 `/v1/messages` 구현이 범위 (Anthropic surface 은 non-goal 에서 제거)
- `/v1/embeddings` 필요 여부 (non-goal 에서 제외 중)

### 13.3 Ollama parallelism 기본값

`model_deployment.concurrency` default (현재 설계: 4). GPU 메모리 기준 검증 필요. 24b 모델 1개 생성의 VRAM footprint × N 이 GPU 한계 이내인지 확인 후 확정.

**3개 결정 확인 후 M0 착수.**
