# Lite Harness Gateway

**English** · [한국어](README.ko.md)

**The LLM gateway for the Lite Harness closed-network stack.**

Lite Harness Gateway is a fork of [LiteLLM](https://github.com/BerriAI/litellm) that sits between your developers and your models (vLLM, Ollama, an internal OpenAI-compatible server, or a cloud API). Clients speak the OpenAI API to it, people sign in with their company account, and every key, team and member gets a budget and a daily token limit. Everything LiteLLM does still works. This fork only adds the pieces a closed network needed.

## The problem

Running a shared model inside a company needs more than a reverse proxy. Someone has to hand out keys, tie them to real accounts, stop one person or team from eating the whole GPU for the day, and see who used what. LiteLLM covers most of that, but a few parts assume a different setup. SSO for more than five users sits behind the paid tier, a token-per-day limit exists but only counts batch jobs, and CLI sign-in (the flow the desktop app uses) only works when an external IdP is reachable.

## The idea

Stay on upstream LiteLLM and change as little as possible.

1. **Keep the upstream proxy.** The fork tracks `BerriAI/litellm` and carries a small set of commits on top, so upstream fixes and providers keep coming in with a merge.
2. **Company accounts through SSO.** Sign-in goes through generic OIDC (Keycloak in our stack). The free-tier cap of five SSO users is configurable with `SSO_MAX_BILLABLE_USERS` (`0` removes it).
3. **A CLI login that also works without an IdP.** When the desktop app starts a CLI SSO login and no SSO provider is configured (or `CLI_SSO_PASSWORD_LOGIN` is set), the gateway shows a LiteLLM email and password form instead of redirecting. The result is the same team-scoped key an SSO login returns.
4. **Daily token limits that actually apply.** `tpd_limit` on a key, a team, or a team member's budget now counts chat completions too. Usage is counted per UTC day and the next request after the limit gets a 429.
5. **Read-only database access for admins over MCP.** A `query_database` virtual MCP tool runs one validated `SELECT` in a read-only transaction with a statement timeout and a row cap. Only keys with proxy admin view can list or call it.

The full list is the commit log on top of upstream:

```bash
git log --oneline main..litellm_airgap
```

## Branches

| Branch | What it holds |
|---|---|
| `main` | A mirror of upstream `BerriAI/litellm`. No fork changes. |
| `litellm_airgap` | The fork: `main` plus the commits above. Branch from here and open PRs against it. |

## Install & run

The gateway runs exactly like LiteLLM proxy, with Postgres for keys, teams and spend. Build the image from this repo (the closed network can't pull upstream images, and they don't carry the fork changes):

```bash
git clone -b litellm_airgap https://github.com/kim-taehan/lite-harness-gateway
cd lite-harness-gateway
docker build -t lite-harness-gateway .
```

A minimal `config.yaml` pointing at an OpenAI-compatible server and a local Ollama:

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

The admin UI is at `http://<host>:4000/ui`. For company sign-in, set the generic OIDC variables (`GENERIC_CLIENT_ID`, `GENERIC_CLIENT_SECRET`, `GENERIC_AUTHORIZATION_ENDPOINT`, `GENERIC_TOKEN_ENDPOINT`, `GENERIC_USERINFO_ENDPOINT`, `PROXY_BASE_URL`) to your Keycloak realm, and `SSO_MAX_BILLABLE_USERS=0` to lift the user cap.

Everything else (providers, routing, budgets, logging, every config option) is upstream behavior. See the [LiteLLM docs](https://docs.litellm.ai/docs/simple_proxy) and the [upstream README](https://github.com/BerriAI/litellm#readme).

## Use

**From Lite Harness desktop**, go to Settings → Models → `+ Add provider`, enter `http://<host>:4000/v1` and an API key from the admin UI. Or turn on **SSO login** and sign in with your company account. The app then gets a key for your team and lists the models that key may use.

**From any OpenAI client:**

```bash
curl http://<host>:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-<your-key>" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3.5-122b", "messages": [{"role": "user", "content": "hello"}]}'
```

**Setting a daily token limit** works the same way as other LiteLLM limits, as `tpd_limit` on a key, a team, or a team member budget:

```bash
curl http://<host>:4000/key/generate \
  -H "Authorization: Bearer sk-<master-key>" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<team-id>", "tpd_limit": 2000000}'
```

## Related repositories

Lite Harness is three repositories that ship together:

```
 lite-harness-plugins ──(installers · catalog.json + extension zips)──▶ lite-harness-desktop
                                                                             │  OpenAI-compatible API
                                                                             │  (API key or company SSO)
                                                                             ▼
                                                                     lite-harness-gateway (this repo) ──▶ LLMs (vLLM · Ollama · cloud …)
```

| Repository | Role | Relationship to this repo |
|---|---|---|
| [lite-harness-desktop](https://github.com/kim-taehan/lite-harness-desktop) | The desktop app (Electron) and the Android app (`mobile/`) | The main client. It connects in Settings → Models with an API key, or through **SSO login** (the CLI SSO flow: `/sso/cli/start` → `/sso/key/generate?source=litellm-cli` → `/sso/cli/poll`), which returns a team key and the models that account may use. |
| [lite-harness-plugins](https://github.com/kim-taehan/lite-harness-plugins) | Distribution repo: app installers (`app-v<version>` releases) and extensions (`catalog.json` + `dist/*.zip`) | None directly. Users get the app from here, then point it at this gateway. |
| **lite-harness-gateway** (this repo) | LLM gateway, a [LiteLLM](https://github.com/BerriAI/litellm) fork for the closed-network stack (SSO via Keycloak, key and team budgets, daily token limits) | — |

## Development

Development follows upstream LiteLLM. Setup, tests and lint gates are in [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Branch off `litellm_airgap` with a `litellm_` prefix and open the PR against `litellm_airgap`.

To pull in upstream:

```bash
git fetch upstream            # upstream = https://github.com/BerriAI/litellm
git checkout main && git merge --ff-only upstream/main && git push origin main
git checkout litellm_airgap && git merge main
```

`README.md` and `README.ko.md` belong to the fork. When an upstream merge conflicts on them, keep ours.

[`GATEWAY_DESIGN.md`](GATEWAY_DESIGN.md) is an earlier design for replacing the Python proxy with a standalone Kotlin gateway. That rewrite was dropped (`edf9fbacf3`) in favor of staying on the Python proxy, so read it as background, not as the current architecture.

## Scope & philosophy

- **Upstream first.** A change goes into the fork only when the closed-network stack needs it, and it stays small so upstream merges stay cheap.
- **Same API as LiteLLM.** Clients and admins use the standard LiteLLM endpoints. The fork adds settings, not new surfaces to learn.
- **Not a new gateway.** For anything this README doesn't mention, the upstream docs are the reference.
