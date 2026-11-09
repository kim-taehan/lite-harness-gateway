# tests/airgap

fork 전용 검사다. upstream 의 `tests/unit/` 미러 규칙을 따르지 않는다. 규칙 본문은 `.claude/rules/` 에 있다

`fork_diff.py` 가 "fork 코드" 를 정한다. `origin/main`(upstream)과의 merge-base 대비 바뀐 파일과 더한 줄이고, 아직 커밋하지 않은 수정과 새 파일도 넣는다. CI 는 `AIRGAP_DIFF_TARGET=HEAD` 로 커밋된 것만 본다. 다른 기준 브랜치를 쓰려면 `AIRGAP_UPSTREAM_REF` 를 준다

`test_fork_rules.py` 는 기준선(`baseline/*.json`, 파일별 개수)과 비교한다. 늘어도 실패하고, 줄었는데 기준선을 그대로 두어도 실패한다. 갱신은 `UPDATE_AIRGAP_BASELINE=1 .venv/bin/python -m pytest tests/airgap -q`

`slow_gate.py` 는 pytest 플러그인이다(`-p tests.airgap.slow_gate`). fork 가 만든 테스트 파일은 테스트 본문(call) 합이 3초, 모든 테스트 하나는 준비·정리를 합쳐 2초를 넘으면 실패한다. 넘은 파일만 혼자 최대 3번 다시 재서 가장 빠른 값으로 판정한다. upstream 이 만든 테스트 파일은 파일 한도를 걸지 않는다

`test_hooklib.py` 는 `.claude/hooks/` 의 판정 함수를 검사한다. 훅은 시스템 `python3`(3.9)로 돌므로 표준 라이브러리만 쓰고 3.9 문법을 지킨다
