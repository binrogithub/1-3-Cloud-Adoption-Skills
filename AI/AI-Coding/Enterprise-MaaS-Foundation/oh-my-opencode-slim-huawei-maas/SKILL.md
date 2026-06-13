---
name: oh-my-opencode-slim-huawei-maas
description: "Bootstrap AI coding stack: deploy LiteLLM proxy (via LiteLLM-Huawei-MaaS-Proxy skill), install opencode + oh-my-opencode-slim, mint virtual key, wire everything. Supports multi-key MaaS load balancing. TRIGGER on: opencode + Huawei MaaS setup, full-stack bootstrap, oh-my-opencode-slim-huawei-maas, deploy-litellm."
---

# oh-my-opencode-slim-huawei-maas Skill

## Overview

Bootstrap a complete AI coding stack on a single host: deploy LiteLLM proxy (via [LiteLLM Huawei MaaS Proxy](https://github.com/binrogithub/1-3-Cloud-Adoption-Skills/tree/main/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy)), install opencode with oh-my-opencode-slim plugin, mint a scoped virtual key, configure end-to-end. Supports multi-key MaaS load balancing for increased throughput. Idempotent — safe to re-run.

## Canonical Installation Paths

Both skills must be installed at these exact paths:
```
/home/
├── LiteLLM-Huawei-MaaS-Proxy/          ← LiteLLM proxy deployment
└── oh-my-opencode-slim-huawei-maas/    ← this project
```

These paths are enforced — no search, no fallback. The LiteLLM proxy is always at `/home/LiteLLM-Huawei-MaaS-Proxy`.

## Installation Source

Both skills are extracted from the monorepo `https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git`:

```bash
MONOREPO="https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git"
TEMP_DIR="/home/1-3-Cloud-Adoption-Skills"

git clone --depth 1 "$MONOREPO" "$TEMP_DIR"
cp -r "$TEMP_DIR/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy" /home/LiteLLM-Huawei-MaaS-Proxy
cp -r "$TEMP_DIR/AI/AI-Coding/oh-my-opencode-slim-huawei-maas" /home/oh-my-opencode-slim-huawei-maas
rm -rf "$TEMP_DIR"
```

## Three Scenarios

| Scenario | Detection | Action |
|----------|-----------|--------|
| LiteLLM running | Health endpoint responds | Resolve master key, skip deploy |
| LiteLLM deployed but offline | Docker container exists (stopped) OR compose + .env exist at `/home/LiteLLM-Huawei-MaaS-Proxy` | `docker compose up -d`, resolve master key |
| No LiteLLM | No container, no files at canonical path | Extract from monorepo, init_env.sh, docker compose up -d |

In all scenarios, `LITELLM_MASTER_KEY` is required to mint the opencode virtual key. If not found in env/files, the user is prompted.

## Prerequisites

| # | Condition | Check | If Missing |
|---|-----------|-------|------------|
| 1 | bun | `bun --version` | https://bun.sh |
| 2 | jq | `jq --version` | https://stedolan.github.io/jq/ |
| 3 | Docker + Compose V2 | `docker compose version` | https://docs.docker.com/engine/install/ |
| 4 | git | `git --version` | install via package manager |
| 5 | python3 | `python3 --version` | install Python 3 |
| 6 | HUAWEI_MAAS_API_KEY | `[ -n "$HUAWEI_MAAS_API_KEY" ]` | export from Huawei Cloud console |
| 7 | HUAWEI_MAAS_EXTRA_API_KEYS (optional) | — | comma-separated extra MaaS keys for load balancing |

## Procedure

### Step 1: Verify prerequisites
- **Guard**: All 6 checks pass
- **Action**: Run each check; remediate failures
- **Post-condition**: bun, jq, Docker, git, python3 installed; HUAWEI_MAAS_API_KEY set

### Step 2: Deploy LiteLLM proxy
- **First**: Set `LITELLM_DIR=/home/LiteLLM-Huawei-MaaS-Proxy` (canonical path)
- **Guard**: `curl -sf http://127.0.0.1:4000/health/liveliness` succeeds
- **If guard passes** (running): Resolve LITELLM_MASTER_KEY (see below), skip deployment
- **If guard fails, but Docker container exists** (stopped): `docker compose up -d`, wait for healthy, resolve master key
- **If guard fails, but compose + .env exist** at `$LITELLM_DIR` (containers removed via `compose down`): `docker compose up -d`, wait for healthy, resolve master key
- **If guard fails, nothing found** (fresh): Extract from monorepo into `$LITELLM_DIR`, run `scripts/init_env.sh --ci`, `docker compose up -d`
- **In all cases**: If LITELLM_MASTER_KEY not found automatically, prompt user
- **Post-condition**: LiteLLM healthy on `:4000`, LITELLM_MASTER_KEY available
- **Failure modes**: monorepo clone fails → check network; Docker Compose fails → check ports 4000/5432/9090/3000; health fails → `docker compose logs litellm`

#### Master Key Resolution

| Priority | Source | Location |
|----------|--------|----------|
| 1 | Environment | `$LITELLM_MASTER_KEY` |
| 2 | `.master-key` file | `$LITELLM_DIR/.master-key` |
| 3 | `.env` file | `$LITELLM_DIR/.env` |
| 4 | Interactive prompt | User enters key |

### Step 3: Install opencode
- **Guard**: `command -v opencode` succeeds
- **Action**: `bun install -g opencode`

### Step 4: Install oh-my-opencode-slim plugin
- **Guard**: `~/.config/opencode/oh-my-opencode-slim.json` exists
- **Action**: `bunx oh-my-opencode-slim@1.1.1 install`

### Step 5: Acquire virtual key
- **Guard**: Existing opencode.jsonc has a LiteLLM apiKey starting with `sk-` that passes a test completion
- **Action**: Reuse if valid; otherwise mint unlimited virtual key via `scripts/mint-virtual-key.sh --no-budget`
- **Note**: Virtual key has no budget cap (unlimited) — budget enforcement is done at the LiteLLM model/config level if needed
- **Failure modes**: key expired → mint new; LITELLM_MASTER_KEY missing → prompt

### Step 6: Write opencode.jsonc
- **Guard**: opencode.jsonc exists with valid LiteLLM apiKey and all 5 models in both providers
- **Action**: Apply jq substitution on template (see below)
- **Post-condition**: Valid JSON, chmod 600

### Step 7: Write oh-my-opencode-slim.json
- **Guard**: oh-my-opencode-slim.json exists with `preset == "LiteLLM-Huawei-MaaS"` and `council.presets` defined
- **Action**: Copy `assets/config/oh-my-opencode-slim.json.example` to `~/.config/opencode/`
- **Post-condition**: All 4 presets defined, default is LiteLLM-Huawei-MaaS, council configured

### Step 8: Validate
- **Action**: `scripts/validate.sh` — all checks must pass (0 failures)

### Step 9: Run opencode and verify
- **Action**: `opencode` — verify "LiteLLM-Huawei-MaaS" preset active in status bar

## Core Rules

1. **Never commit real keys** — use `<placeholder>` in examples
2. **All agent traffic through LiteLLM** — proxy as sole egress for spend tracking
3. **LiteLLM provider uses `@ai-sdk/openai-compatible`** — NOT built-in `openai`
4. **Model keys use `openai/<model>` format** in LiteLLM provider (matching litellm_config.yaml)
5. **Model references in presets use `LiteLLM/openai/<model>`** (3-part)
6. **LiteLLM baseURL is `http://0.0.0.0:4000`** (no `/v1` suffix — SDK adds it; scripts use `127.0.0.1:4000` for curl)
7. **Disable `explore` and `general` agents** via `agent` (singular) with `disable: true`
8. **Enable LSP** (`"lsp": true`)
9. **Use virtual keys, not master key**, for opencode — unlimited budget (no `max_budget`)
10. **Use `jq --arg` for JSON substitution** — never `sed`
11. **Same-host only** — LiteLLM and opencode on the same machine

## Substitution Rules

Replace placeholders in `assets/config/opencode.jsonc.example` using `jq --arg`:

```bash
jq --arg vk "$VIRTUAL_KEY" --arg mk "$MAAS_KEY" \
  '.provider.LiteLLM.options.apiKey = $vk |
   .provider["Huawei-MaaS"].options.apiKey = $mk' \
  assets/config/opencode.jsonc.example > ~/.config/opencode/opencode.jsonc
```

| Placeholder | Source |
|-------------|--------|
| `<LITELLM_VIRTUAL_KEY>` | Virtual key from Step 5 |
| `<HUAWEI_MAAS_API_KEY>` | `$HUAWEI_MAAS_API_KEY` env var |

## Presets

Four presets in oh-my-opencode-slim.json — two via LiteLLM proxy (default), two direct to MaaS (debugging/fallback):

| Preset | Models | Route |
|--------|--------|-------|
| **LiteLLM-Huawei-MaaS** (default) | All 5 | LiteLLM proxy → MaaS |
| **LiteLLM-Huawei-MaaS-Lite** | 3 (no v4-pro/v4-flash) | LiteLLM proxy → MaaS |
| **Huawei-MaaS** | All 5 | Direct to MaaS (no proxy) |
| **Huawei-MaaS-Lite** | 3 (no v4-pro/v4-flash) | Direct to MaaS (no proxy) |

Switch at runtime: `/preset LiteLLM-Huawei-MaaS-Lite`

### LiteLLM-Huawei-MaaS (default) — Agent Assignments

| Agent | Model | Variant | Why |
|-------|-------|---------|-----|
| orchestrator | LiteLLM/openai/glm-5.1 | high | Strongest reasoning, delegation |
| oracle | LiteLLM/openai/deepseek-v4-pro | max | Deep thinking, architecture |
| council | LiteLLM/openai/deepseek-v4-pro | high | Independent deep review |
| librarian | LiteLLM/openai/deepseek-v3.2 | low | Highest RPM, cheapest, docs |
| explorer | LiteLLM/openai/deepseek-v4-flash | low | Fast, 1M context |
| designer | LiteLLM/openai/glm-5 | medium | General model, UI/UX |
| fixer | LiteLLM/openai/deepseek-v4-flash | high | Fast execution |

### Fallback Chains

| Agent | Primary | Fallback |
|-------|---------|----------|
| oracle | deepseek-v4-pro | glm-5.1 |
| council | deepseek-v4-pro | glm-5.1 |
| explorer | deepseek-v4-flash | deepseek-v3.2 |
| fixer | deepseek-v4-flash | glm-5 |

### Council

| Councillor | Model | Variant |
|------------|-------|---------|
| alpha | LiteLLM/openai/deepseek-v4-pro | high |
| beta | LiteLLM/openai/glm-5.1 | high |
| gamma | LiteLLM/openai/deepseek-v3.2 | high |

## Post-Bootstrap

| Service | URL | Credentials |
|---------|-----|-------------|
| LiteLLM Proxy | `http://127.0.0.1:4000` | Virtual key (in opencode.jsonc) |
| LiteLLM Admin UI | `http://127.0.0.1:4000/ui` | Master key (from `.master-key`) |
| Prometheus | `http://127.0.0.1:9090` | None |
| Grafana | `http://127.0.0.1:3000` | admin / (from `.env`) |

| Config File | Location | Permissions |
|-------------|----------|-------------|
| opencode.jsonc | `~/.config/opencode/opencode.jsonc` | 600 |
| oh-my-opencode-slim.json | `~/.config/opencode/oh-my-opencode-slim.json` | 600 |

## Repair Playbook

| Symptom | Fix |
|---------|-----|
| LiteLLM won't start | `docker compose ps`, check port conflicts (4000, 5432, 9090, 3000), check `.env` |
| LiteLLM deployed but offline | `docker compose -f /home/LiteLLM-Huawei-MaaS-Proxy/docker-compose.yml up -d` |
| opencode won't start | `jq . ~/.config/opencode/opencode.jsonc`, check `@ai-sdk/openai-compatible` installed |
| Models not found | `curl http://127.0.0.1:4000/v1/models`, compare with litellm_config.yaml |
| Plugin not loaded | Add `"oh-my-opencode-slim"` to plugin array, re-run `bunx oh-my-opencode-slim@1.1.1 install` |
| 401 errors | Mint new virtual key, update opencode.jsonc |
| Wrong preset | Set `"preset": "LiteLLM-Huawei-MaaS"` or run `/preset LiteLLM-Huawei-MaaS` |
| "No presets configured" | Ensure `council.presets` is defined in oh-my-opencode-slim.json |
| Fallback not triggering | Set `fallback.enabled: true`, add chains for v4-model agents |
| Repo clone fails | Verify https://github.com/binrogithub/1-3-Cloud-Adoption-Skills is reachable |
| Requests timing out intermittently | Check `request_timeout` in litellm_config.yaml — should be 600s, not 10s; regenerate with `./scripts/generate_config.sh` |

## Sanitization Rules

1. **Never commit real keys, virtual keys, or bearer tokens**
2. **Use `<HUAWEI_MAAS_API_KEY>`, `<LITELLM_VIRTUAL_KEY>` placeholders in examples**
3. **Mask keys as `<prefix>...<suffix>` in output** — e.g. `sk-abc123...xyz789`
4. **Use `jq --arg` for substitution in scripts, never `sed`**

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| LiteLLM keeps restarting | DB not ready or wrong password | Check `.env`, `docker compose logs db` |
| 401 from proxy | Wrong master key or virtual key | Re-check key, mint new if needed |
| 404 model not found | Wrong model ID | Copy exact name from MaaS console |
| opencode won't start | Wrong provider npm package | Use `@ai-sdk/openai-compatible`, not `openai` |
| Budgets not decrementing | Model pricing is zero | Set non-zero token pricing in litellm_config.yaml |
| Virtual key expired | Duration or budget exceeded | Mint new key with `--no-budget` |
| Intermittent timeout errors from proxy | LiteLLM `request_timeout` too low (default was 10s, should be 600s) | Increase in litellm_config.yaml, regenerate with `generate_config.sh`, restart litellm |

## Verification Exit Criteria

- [ ] LiteLLM proxy healthy on `http://127.0.0.1:4000`
- [ ] opencode.jsonc exists with both providers (LiteLLM + Huawei-MaaS)
- [ ] `provider` key singular, `agent` key singular
- [ ] LiteLLM provider: baseURL `http://0.0.0.0:4000`, valid virtual key, 5 models with `openai/` prefix
- [ ] Huawei-MaaS provider: 5 models without `openai/` prefix
- [ ] oh-my-opencode-slim.json: 4 presets defined, default is LiteLLM-Huawei-MaaS
- [ ] All 7 agent roles have model, variant, skills, mcps
- [ ] explore/general disabled, observer disabled, LSP enabled
- [ ] Fallback chains for oracle, council, explorer, fixer
- [ ] Council presets with alpha/beta/gamma
- [ ] opencode.jsonc chmod 600, no real keys in git

## Cross-Skill References

| Skill | Relationship |
|-------|--------------|
| [LiteLLM Huawei MaaS Proxy](https://github.com/binrogithub/1-3-Cloud-Adoption-Skills/tree/main/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy) | Invoked — LiteLLM proxy deployment |

## Codebase

```
.
├── SKILL.md                                    This file (agent-facing)
├── README.md                                   Human-facing skill card
├── .gitignore                                  Prevent secret commits
├── assets/
│   └── config/
│       ├── opencode.jsonc.example              Template — copy to ~/.config/opencode/
│       └── oh-my-opencode-slim.json.example    Template — copy to ~/.config/opencode/
└── scripts/
    ├── bootstrap.sh                            End-to-end orchestrator (idempotent)
    ├── install.sh                              opencode + plugin + config installer
    ├── mint-virtual-key.sh                     Mint scoped key from LiteLLM
    └── validate.sh                             Validation checks
```
