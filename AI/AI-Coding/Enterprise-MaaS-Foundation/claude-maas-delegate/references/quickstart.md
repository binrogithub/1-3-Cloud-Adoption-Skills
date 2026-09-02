# Installation

Quick start for the self-contained Claude-MaaS Skill package. The host agent
keeps its own provider, model, and authentication; only delegated execution
uses the configured Anthropic-compatible MaaS endpoint.

## Prerequisites

- A POSIX system (macOS, Linux, or WSL).
- Python ≥ 3.7 on PATH.
- An Anthropic-compatible MaaS endpoint URL and API key.

## Install

Interactive (prompts for URL and hidden key):

```sh
./scripts/install.sh
```

Non-interactive (key on stdin, URL on argv):

```sh
printf '%s\n' "$MAAS_KEY" | ./scripts/install.sh --non-interactive \
  --api-url https://maas.example.test/anthropic/v1/messages --agents codex,cursor
```

The installer auto-installs Claude Code if missing (unless `--no-install-claude`),
writes the MaaS client config, installs the delegation Skill into the selected
host agents, and runs `maas-delegate doctor` to confirm the binary is runnable.

## Flags

| Flag | Purpose |
| --- | --- |
| `--api-url URL` | Anthropic-compatible endpoint (HTTPS required; localhost for tests) |
| `--model MODEL` | MaaS model (default `glm-5.2`) |
| `--agents LIST` | Subset of `codex,copilot,cursor,opencode` (default: all) |
| `--non-interactive` | Require `--api-url`; read key as one line on stdin |
| `--no-install-claude` | Fail instead of auto-installing Claude Code |
| `--force` | Replace owned installation files |

The API key is read from stdin, never from argv. Re-running install is idempotent.

## Uninstall

```sh
./scripts/uninstall.sh            # remove project items, retain key + audit
./scripts/uninstall.sh --purge    # also remove key, config, and audit data
```

Uninstall removes only project-owned items and never removes Claude Code, OAuth
tokens, user hooks, MCP, themes, or preferences. Running twice is a no-op.

## Verify

```sh
python3 scripts/verify-skill-release.py .
```

Checks manifest integrity, file hashes, sizes, modes, required entry points,
and forbidden content (secrets, absolute paths, Git metadata, caches).

For full installation details including the bootstrap path, see
[INSTALL.md](INSTALL.md).
