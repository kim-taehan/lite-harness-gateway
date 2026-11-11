# CLI 로그인 한 기기 제한 설계

이슈 #4. 모든 사용자는 기본으로 CLI 로그인을 마지막으로 로그인한 기기 하나에서만 쓴다

## 누구에게 적용하나
- 기본으로 모든 사용자에게 적용한다. 사용자 metadata 에 `cli_single_device` 가 없어도 적용한다
- 관리자가 사용자 metadata 에 `"cli_single_device": false` 를 넣은 사용자만 뺀다(서비스 계정처럼 여러 곳에서 써야 하는 경우). 값이 정확히 JSON `false` 일 때만 빼 준다. 문자열 `"false"`, `null`, `true` 는 적용한다
- 처음에는 "관리자가 true 로 켠 사용자만" 이었다가, 사용자 결정으로 "기본 켜짐, false 만 예외" 로 바꿨다

## 예외로 빼는 법
`"cli_single_device": false` 를 넣으면서 `cli_active_login_id` 를 함께 지운다. `cli_active_login_id` 를 남긴 채 뺐다가 나중에 예외를 풀면, 마지막으로 기록된 기기만 살고 나머지는 바로 끊긴다. 예외인 사용자가 CLI 로그인을 한 번 하면 남은 `cli_active_login_id` 는 그때 지워진다

## 무엇을 CLI 로그인으로 세나
CLI 용 자격 증명(`lite login` 이 받는 세션 토큰)을 새로 만드는 모든 경로를 로그인 한 번으로 센다
- `lite login` (`/sso/cli/poll`)
- Claude Code 로그인 (`/claude_code_gateway/oauth/token` device code)
- `lite login --pkce` 와 같은 네이티브 클라이언트 OAuth: authorization code, token exchange(IdP 토큰 교환), jwt-bearer(ID-JAG)
웹 관리 화면 로그인과 관리자가 발급한 `sk-` 키는 세지 않고 영향도 없다

## 로그인 번호
- 로그인마다 무작위 로그인 번호를 만든다(`secrets.token_urlsafe(16)`)
- 번호는 CLI 세션 토큰의 `metadata.cli_login_id` 에 들어간다. upstream 의 토큰 타입(`UserAPIKeyAuth`)은 바꾸지 않고 원래 있던 `metadata` 칸을 쓴다
- 적용 대상 사용자면 사용자 metadata 의 `cli_active_login_id` 에 그 번호를 적는다. 예외인 사용자는 적지 않는다(남은 번호는 지운다). DB 스키마는 그대로다
- 번호는 비밀 값이 아니다. 번호만으로는 아무것도 할 수 없고, 토큰은 따로 암호화돼 있다

## 갱신은 같은 로그인
- 갱신(refresh token)은 새 로그인이 아니다. 같은 번호로 새 토큰을 만든다
- 번호를 refresh token 의 rotation chain id(`family`)로 쓴다. 새 로그인은 chain 을 번호로 시작하고, 갱신은 chain 을 이어받으므로 번호도 그대로 이어진다. 그래서 upstream 의 refresh token 형식(`SessionPrincipal`, claim)은 바꾸지 않는다
- 이 기능 전에 만든 chain 은 family 가 첫 토큰의 jti 다. 그 chain 의 갱신 토큰은 그 jti 를 번호로 갖는데, 그 사용자가 새로 로그인한 뒤라면 번호가 달라 막힌다. 첫 로그인 전이면 막히지 않는다

## 요청마다 검사
- 세션 토큰의 권한을 사용자·팀 행에서 다시 읽는 단계(`_refresh_session_token_grants`)에서 비교한다. 이 단계는 원래 요청마다 사용자 행을 캐시와 함께 읽는다
- 적용 대상 사용자이고 metadata 에 번호가 있는데 토큰의 번호와 다르면 401. 메시지: "다른 기기에서 로그인해 이 기기의 로그인이 끝났습니다. `lite login` 을 다시 하세요". 토큰·키 값은 넣지 않는다
- metadata 에 번호가 아직 없으면(배포 뒤 그 사람의 첫 CLI 로그인 전) 모든 토큰을 그대로 허용한다. 그래서 배포 순간 모든 사용자가 한꺼번에 끊기지 않고, 각자 다음 CLI 로그인부터 그 기기 하나만 남는다
- 번호가 없는 토큰(이 기능 전에 만든 토큰)은 metadata 에 번호가 생긴 뒤부터 막힌다
- 캐시의 사용자 행이 방금 한 로그인보다 오래됐을 수 있다. 다르면 막기 전에 DB 에서 한 번 더 읽어 확인한다. 그래서 새 기기는 바로 쓰고, 이전 기기는 캐시가 바뀌는 대로(보통 1분 안) 막힌다
- DB 를 다시 읽는 건 번호가 다를 때뿐이다. 이미 끊긴 기기는 요청마다 다르므로 그때마다 writer DB 를 한 번 읽는다. 끊긴 CLI 는 401 을 받고 멈추므로 범위가 작다고 보고 의도로 둔다
- 다시 읽기가 실패하면(DB 오류) 막지 않고 통과시킨다. 같은 단계의 권한 다시 읽기가 사용자 행을 못 읽을 때 기존 권한으로 통과시키는 것과 같다. 경고 로그를 남긴다

## 실패할 때
- 로그인 기록(사용자 metadata 쓰기)이 DB 오류로 실패해도 로그인은 성공시킨다. 경고 로그만 남기고, 이전 기기는 다음 로그인이 기록될 때까지 살아 있다. 정책 기록 때문에 로그인 자체가 막히지 않게 하려는 선택이다
- 네이티브 OAuth 경로는 일회용 표시(claim)가 성공한 뒤에 기록한다. 재사용(replay)된 code 가 이미 로그인한 기기를 끊지 못하게 하려는 것이다
- 기록은 사용자 행을 읽고 metadata 를 통째로 다시 쓴다. 같은 순간 관리자가 metadata 를 고치면 한쪽이 덮일 수 있다(드묾)

## 한계
- refresh token 이 없는 jwt-bearer(ID-JAG) 와, 클라이언트가 반복해서 부르는 token exchange 는 받을 때마다 새 로그인으로 센다. 한 사용자가 한 기기에서 이 방식을 쓰는 프로세스를 둘 띄우면 서로를 번갈아 끊는다
- 사용자 metadata 를 고칠 수 있는 사람은 `"cli_single_device": false` 를 넣어 제한을 풀 수 있다. `/user/update` 는 관리자 전용 경로 묶음에 있어 일반 사용자(internal_user)와 internal_user_viewer 는 경로 검사에서 막히고, proxy_admin_viewer 는 `user_email` 만 바꿀 수 있다. 다만 조직 관리자(org admin)는 요청에 자기 `organization_id` 를 넣으면 경로 검사를 통과하고, `/user/update` 가 자기 행 수정을 허용하며 metadata 는 막는 필드에 없으므로 자기 metadata 에 false 를 넣을 수 있다(코드로 확인, 실제 호출은 하지 않음). 막는 방법은 따로 정한다
- 기본 켜짐이라 CLI 로그인마다 사용자 행 metadata 를 한 번 쓴다(예외인 사용자는 남은 번호가 있을 때만)

## 코드 위치
- 판정과 기록: `litellm/proxy/auth/cli_single_device.py`
- upstream 파일에는 호출만 더했다: 토큰 만들기(`auth_checks.py`), 요청 검사(`user_api_key_auth.py`), 로그인 경로(`ui_sso.py`, `anthropic_endpoints/gateway_endpoints.py`, `_experimental/mcp_server/gateway_dcr_flow.py`, `_experimental/mcp_server/proxy_api_credentials.py`)
