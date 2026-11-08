#!/bin/sh
# upstream 에서 온 GitHub Actions 워크플로를 모두 끄고 airgap-ci.yml 만 남긴다 (.claude/rules/workflow.md 13번)
# upstream 동기화로 새 워크플로가 들어올 때마다 다시 돌린다. 이미 꺼진 것은 건너뛴다
set -eu
repo=kim-taehan/lite-harness-gateway
gh=$(command -v gh || echo /opt/homebrew/bin/gh)
GH_TOKEN=$("$gh" auth token -u kim-taehan)
export GH_TOKEN

"$gh" api --paginate "repos/$repo/actions/workflows" --jq '.workflows[] | select(.state == "active") | [.id, .path] | @tsv' |
while IFS="$(printf '\t')" read -r id path; do
    case "$path" in
        .github/workflows/airgap-ci.yml) continue ;;
    esac
    "$gh" api -X PUT "repos/$repo/actions/workflows/$id/disable" >/dev/null
    echo "disabled $path"
done
