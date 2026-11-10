# CLI 로그인 한 기기 제한 설계

이슈 #4. 관리자가 정한 사용자는 CLI 로그인을 마지막으로 로그인한 기기 하나에서만 쓴다

## 켜는 법
관리자가 사용자 metadata 에 `"cli_single_device": true` 를 넣는다. 값이 정확히 `true` 일 때만 적용한다(문자열 `"true"` 는 적용하지 않는다). 없거나 false 면 지금처럼 기기 수 제한이 없다

## 무엇을 CLI 로그인으로 세나
CLI 용 자격 증명(`lite login` 이 받는 세션 토큰)을 새로 만드는 모든 경로를 로그인 한 번으로 센다
- `lite login` (`/sso/cli/poll`)
- Claude Code 로그인 (`/claude_code_gateway/oauth/token` device code)
- `lite login --pkce` 와 같은 네이티브 클라이언트 OAuth: authorization code, token exchange(IdP 토큰 교환), jwt-bearer(ID-JAG)
웹 관리 화면 로그인과 관리자가 발급한 `sk-` 키는 세지 않고 영향도 없다

## 로그인 번호
- 로그인마다 무작위 로그인 번호를 만든다(`secrets.token_urlsafe(16)`)
- 번호는 CLI 세션 토큰의 `metadata.cli_login_id` 에 들어간다. upstream 의 토큰 타입(`UserAPIKeyAuth`)은 바꾸지 않고 원래 있던 `metadata` 칸을 쓴다
- 켠 사용자면 사용자 metadata 의 `cli_active_login_id` 에 그 번호를 적는다. 켜지 않은 사용자는 아무것도 적지 않는다. DB 스키마는 그대로다
- 번호는 비밀 값이 아니다. 번호만으로는 아무것도 할 수 없고, 토큰은 따로 암호화돼 있다

## 갱신은 같은 로그인
- 갱신(refresh token)은 새 로그인이 아니다. 같은 번호로 새 토큰을 만든다
- 번호를 refresh token 의 rotation chain id(`family`)로 쓴다. 새 로그인은 chain 을 번호로 시작하고, 갱신은 chain 을 이어받으므로 번호도 그대로 이어진다. 그래서 upstream 의 refresh token 형식(`SessionPrincipal`, claim)은 바꾸지 않는다
- 이 기능 전에 만든 chain 은 family 가 첫 토큰의 jti 다. 그 chain 의 갱신 토큰은 그 jti 를 번호로 갖는데, 켠 사용자가 새로 로그인한 뒤라면 번호가 달라 막힌다. 첫 로그인 전이면 막히지 않는다

## 요청마다 검사
- 세션 토큰의 권한을 사용자·팀 행에서 다시 읽는 단계(`_refresh_session_token_grants`)에서 비교한다. 이 단계는 원래 요청마다 사용자 행을 캐시와 함께 읽는다
- 켠 사용자이고 metadata 에 번호가 있는데 토큰의 번호와 다르면 401. 메시지: "다른 기기에서 로그인해 이 기기의 로그인이 끝났습니다. `lite login` 을 다시 하세요". 토큰·키 값은 넣지 않는다
- 켠 사용자라도 metadata 에 번호가 아직 없으면(켠 뒤 첫 로그인 전) 모든 토큰을 그대로 허용한다
- 번호가 없는 토큰(이 기능 전에 만든 토큰)은 metadata 에 번호가 생긴 뒤부터 막힌다
- 캐시의 사용자 행이 방금 한 로그인보다 오래됐을 수 있다. 다르면 막기 전에 DB 에서 한 번 더 읽어 확인한다. 그래서 새 기기는 바로 쓰고, 이전 기기는 캐시가 바뀌는 대로(보통 1분 안) 막힌다. DB 를 다시 읽는 건 번호가 다를 때뿐이다

## 실패할 때
- 로그인 기록(사용자 metadata 쓰기)이 DB 오류로 실패해도 로그인은 성공시킨다. 경고 로그만 남기고, 이전 기기는 다음 로그인이 기록될 때까지 살아 있다. 정책 기록 때문에 로그인 자체가 막히지 않게 하려는 선택이다
- 네이티브 OAuth 경로는 일회용 표시(claim)가 성공한 뒤에 기록한다. 재사용(replay)된 code 가 이미 로그인한 기기를 끊지 못하게 하려는 것이다
- 기록은 사용자 행을 읽고 metadata 를 통째로 다시 쓴다. 같은 순간 관리자가 metadata 를 고치면 한쪽이 덮일 수 있다(드묾)

## 코드 위치
- 판정과 기록: `litellm/proxy/auth/cli_single_device.py`
- upstream 파일에는 호출만 더했다: 토큰 만들기(`auth_checks.py`), 요청 검사(`user_api_key_auth.py`), 로그인 경로(`ui_sso.py`, `anthropic_endpoints/gateway_endpoints.py`, `_experimental/mcp_server/gateway_dcr_flow.py`, `_experimental/mcp_server/proxy_api_credentials.py`)
