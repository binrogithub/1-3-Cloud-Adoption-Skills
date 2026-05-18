# oh-my-opencode-slim-huawei-maas

Bootstrap a complete AI coding stack on a single host: LiteLLM proxy + opencode + oh-my-opencode-slim, all wired to Huawei Cloud MaaS.

This skill is an **idempotent bootstrap**. Running `scripts/bootstrap.sh` deploys LiteLLM (via the [LiteLLM Huawei MaaS Proxy](../LiteLLM-Huawei-MaaS-Proxy/) skill), installs opencode with the oh-my-opencode-slim plugin, mints a scoped virtual key, configures dual providers with four presets, and validates the full stack. Safe to re-run.

## Skill Level

**Level 2 — Tested in production.** The bootstrap scripts, config templates, and validation checks come from a working MaaS-backed opencode deployment.

## Applicable Scenario

Use this when a developer workstation needs:

- a complete AI coding environment from bare machine to working opencode
- all model traffic routed through LiteLLM for spend tracking and budget enforcement
- multi-agent orchestration with oh-my-opencode-slim presets and fallback chains
- virtual key isolation instead of exposing the raw MaaS key
- fallback when deepseek-v4 models are unavailable

## Business Problem Addressed

- No single command to go from bare machine to working AI coding environment
- opencode defaults to OpenAI/Anthropic — no Huawei MaaS integration
- No spend tracking or budget enforcement when calling MaaS directly
- No fallback when deepseek-v4 models are unavailable
- No model failover on timeout or rate limit errors

## Required Cloud and Domain Knowledge

- Huawei Cloud ModelArts MaaS (ap-southeast-1)
- LiteLLM proxy deployment via Docker Compose
- opencode CLI and oh-my-opencode-slim plugin configuration
- @ai-sdk/openai-compatible provider for custom endpoints

## Required AI, Tools, and Platforms

| Tool | Version | Purpose |
|---|---|---|
| opencode | latest | AI coding CLI |
| oh-my-opencode-slim | v1.1.1 | Agent orchestration plugin |
| LiteLLM proxy | v1.83.14 | API gateway (deployed by this skill) |
| bun | latest | JavaScript runtime |
| jq | latest | JSON-safe config substitution |
| Docker + Compose V2 | latest | Container runtime for LiteLLM |

## Workflow / Method

1. Verify prerequisites (bun, jq, Docker, git, python3, env vars)
2. Deploy LiteLLM proxy — find existing or clone + init + compose up
3. Install opencode + oh-my-opencode-slim plugin
4. Mint unlimited virtual key from LiteLLM
5. Configure opencode.jsonc with LiteLLM + Huawei-MaaS providers
6. Configure oh-my-opencode-slim.json with 4 presets, fallback chains, council
7. Validate all configuration and connectivity
8. Run opencode and verify preset is active

## Expected Outputs

- LiteLLM Docker Compose stack running (db, litellm, prometheus, grafana)
- opencode.jsonc with dual providers, all 5 models, chmod 600
- oh-my-opencode-slim.json with 4 presets, fallback chains, council councillors
- Virtual key minted from LiteLLM (unlimited budget, no duration)
- All 7 agent roles mapped to MaaS models

## Validation Method

See SKILL.md Verification Exit Criteria. Run `scripts/validate.sh` for automated validation.

## Reusable Assets

| Asset | Location | Purpose |
|-------|----------|---------|
| `opencode.jsonc.example` | `assets/config/` | Template for opencode provider + model config |
| `oh-my-opencode-slim.json.example` | `assets/config/` | Template for presets, fallback, council config |
| `bootstrap.sh` | `scripts/` | End-to-end idempotent orchestrator |
| `install.sh` | `scripts/` | opencode + plugin + config installer |
| `mint-virtual-key.sh` | `scripts/` | Mint scoped key from LiteLLM |
| `validate.sh` | `scripts/` | Automated validation checks |

## KPIs / Evaluation Metrics

| Metric | Target | Description |
|---|---|---|
| Bootstrap success | First run | Full stack deploys without manual intervention |
| Preset activation | First try | LiteLLM-Huawei-MaaS preset loads without errors |
| Model availability | 5/5 | All models reachable via LiteLLM proxy |
| Spend tracking | 100% | All opencode traffic logged through LiteLLM |

## Common Risks and Troubleshooting

| Risk | Impact | Mitigation |
|---|---|---|
| LiteLLM won't start | Bootstrap fails at Step 3 | Check Docker, port conflicts (4000, 5432, 9090, 3000) |
| opencode won't start | Cannot run AI coding | `jq . ~/.config/opencode/opencode.jsonc` — check `@ai-sdk/openai-compatible` |
| Models not found | 404 errors at inference | `curl http://127.0.0.1:4000/v1/models` — compare with litellm_config.yaml |
| 401 errors | Auth failure | Mint new key: `./scripts/mint-virtual-key.sh` |
| v4 models unavailable | Deep models fail | Switch to LiteLLM-Huawei-MaaS-Lite preset |
| Plugin not loaded | No presets available | Re-run: `bunx oh-my-opencode-slim@1.1.1 install` |
| Wrong preset | Not using LiteLLM route | Run `/preset LiteLLM-Huawei-MaaS` |

## Quick Start

### From scratch (fresh machine)

```bash
git clone https://github.com/wallacelw/oh-my-opencode-slim-huawei-maas.git
cd oh-my-opencode-slim-huawei-maas
export HUAWEI_MAAS_API_KEY="your-key-from-huawei-console"
./scripts/bootstrap.sh
opencode
```

### LiteLLM already running on this machine

```bash
export HUAWEI_MAAS_API_KEY="your-key"
./scripts/bootstrap.sh    # auto-detects LiteLLM on :4000, skips deployment
```

### Non-interactive (CI/CD)

```bash
./scripts/bootstrap.sh --maas-key="$MAAS_KEY" --virtual-key="sk-..."
```

### Validate an existing setup

```bash
./scripts/validate.sh
```

## Presets

| Preset | Models | Route |
|--------|--------|-------|
| **LiteLLM-Huawei-MaaS** (default) | All 5 | LiteLLM proxy → MaaS |
| **LiteLLM-Huawei-MaaS-Lite** | 3 (no v4-pro/v4-flash) | LiteLLM proxy → MaaS |
| **Huawei-MaaS** | All 5 | Direct to MaaS |
| **Huawei-MaaS-Lite** | 3 (no v4-pro/v4-flash) | Direct to MaaS |

Switch at runtime:
```
/preset LiteLLM-Huawei-MaaS-Lite
/preset Huawei-MaaS
```

## Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| LiteLLM Proxy | `http://127.0.0.1:4000` | Virtual key (in opencode.jsonc) |
| LiteLLM Admin UI | `http://127.0.0.1:4000/ui` | Master key (from `.master-key`) |
| Prometheus | `http://127.0.0.1:9090` | None |
| Grafana | `http://127.0.0.1:3000` | admin / (from `.env`) |

## Config Files

| File | Location | Permissions |
|------|----------|-------------|
| opencode.jsonc | `~/.config/opencode/opencode.jsonc` | 600 |
| oh-my-opencode-slim.json | `~/.config/opencode/oh-my-opencode-slim.json` | 600 |
